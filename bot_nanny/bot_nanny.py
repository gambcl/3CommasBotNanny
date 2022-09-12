import logging
import requests  # type: ignore
import rich  # type: ignore
import time

from . import __version__
from enum import Enum
from py3cw.request import Py3CW  # type: ignore
from typing import Dict, Set

logger = logging.getLogger(__name__)

# 3Commas API documentation:
# https://github.com/3commas-io/3commas-official-api-docs
THREE_COMMAS_API_INTERVAL_SECONDS = 1
THREE_COMMAS_BOTS_BATCH_SIZE = 100
THREE_COMMAS_DEALS_BATCH_SIZE = 1000


class MessageType(Enum):
    """
    Enum for identifying message levels.
    """
    DEBUG = 0,
    INFO = 1,
    SUCCESS = 2,
    WARNING = 3,
    ERROR = 4


class BotNanny:
    """
    Fetches DCA Bot Deals from your 3Commas account and updates the SL value if the PnL has reached
    a specified minimum value. Useful for trimming losses when running TBO Switch strategy.
    """
    config: Dict
    api_key: str
    api_secret: str
    interval_seconds: int
    target_pnl_percent: float
    adjusted_sl_percent: float
    selected_account_ids: Set[int]
    selected_bot_ids: Set[int]
    selected_deal_ids: Set[int]

    def __init__(self, config: Dict):
        """
        Initialises a BotNanny instance with a config dictionary.

        :param config: Config dictionary (usually read from a config.toml file).
        """
        self.config = config
        if not config:
            raise ValueError("Invalid config")
        self.interval_seconds = self.config.get("interval_seconds", 600)
        self.target_pnl_percent = self.config.get("target_pnl_percent", 4.0)
        self.adjusted_sl_percent = self.config.get("adjusted_sl_percent", 1.0)

        if "three_commas" not in config:
            raise RuntimeError("Config is missing 'three_commas' section")
        three_commas_config = config["three_commas"]

        if "api_key" not in three_commas_config:
            raise RuntimeError("Config is missing 'api_key' value in 'three_commas' section")
        self.api_key = three_commas_config.get("api_key", None)

        if "api_secret" not in three_commas_config:
            raise RuntimeError("Config is missing 'api_secret' value in 'three_commas' section")
        self.api_secret = three_commas_config.get("api_secret", None)

        self.selected_account_ids = set(three_commas_config.get("account_ids", []))
        self.selected_bot_ids = set(three_commas_config.get("bot_ids", []))
        self.selected_deal_ids = set(three_commas_config.get("deal_ids", []))

        self.py3cw = Py3CW(
            key=self.api_key,
            secret=self.api_secret,
            request_options={
                'request_timeout': 10,
                'nr_of_retries': 1,
                'retry_status_codes': [502],
                'retry_backoff_factor': 0.1
            }
        )

    def run(self):
        """
        Start processing Bot Deals.
        """
        self.output_startup_message()
        self._send_telegram_message(f"BotNanny {__version__} started")
        while True:
            try:
                discovered_bot_ids = self._fetch_bot_ids_for_account_ids(self.selected_account_ids)
                bot_ids = discovered_bot_ids.union(self.selected_bot_ids)
                discovered_deal_ids = self._fetch_deal_ids_for_bot_ids(bot_ids)
                deal_ids = discovered_deal_ids.union(self.selected_deal_ids)
                self._process_deal_ids(deal_ids)
            except Exception as ex:
                self.output_message(MessageType.ERROR, f"Caught Exception in BotNanny.run(): {ex}")
            finally:
                # Sleep until next check.
                self.output_message(MessageType.INFO, f"Sleeping for {self.interval_seconds}s ...")
                time.sleep(self.interval_seconds)

    def _fetch_bot_ids_for_account_ids(self, account_ids: Set[int]) -> Set[int]:
        """
        Fetches all Bot IDs for the specified Account IDs.

        :param account_ids: A set containing 3Commas Account IDs.
        :return: A set containing 3Commas Bot IDs.
        """
        bot_ids = set()
        for account_id in account_ids:
            try:
                time.sleep(THREE_COMMAS_API_INTERVAL_SECONDS)
                error, data = self.py3cw.request(
                    entity="accounts",
                    action="account_info",
                    action_id=f"{account_id}"
                )
                if error:
                    self.output_message(
                        MessageType.ERROR,
                        f"Failed to fetch account info for account id {account_id}: {error}"
                    )
                    continue

                account_name = data["name"]

                self.output_message(MessageType.INFO, f"Fetching bot ids for account '{account_name}'")
                account_bot_ids = set()
                completed = False
                offset = 0
                while not completed:
                    error, data = self.py3cw.request(
                        entity="bots",
                        action="",
                        payload={
                            "limit": THREE_COMMAS_BOTS_BATCH_SIZE,
                            "offset": offset,
                            "account_id": account_id
                        }
                    )
                    if error:
                        self.output_message(
                            MessageType.ERROR,
                            f"Failed to fetch bot ids for account '{account_name}': {error}"
                        )
                        completed = True  # Give up on this account if we hit errors.
                    else:
                        for bot in data:
                            bot_name = bot["name"]
                            self.output_message(MessageType.INFO, f"Found bot '{bot_name}'")
                            account_bot_ids.add(bot["id"])
                        offset += len(data)  # Increase offset for next call.
                        completed = len(data) < THREE_COMMAS_BOTS_BATCH_SIZE  # Have we finished?
                self.output_message(
                    MessageType.DEBUG,
                    f"Found {len(account_bot_ids)} bots for account '{account_name}'"
                )
                bot_ids.update(account_bot_ids)
            except Exception as ex:
                self.output_message(
                    MessageType.ERROR,
                    f"Caught Exception fetching bot ids for account id {account_id}: {ex}"
                )
        return bot_ids

    def _fetch_deal_ids_for_bot_ids(self, bot_ids: Set[int]) -> Set[int]:
        """
        Fetches all Bot Deal IDs for the specified Bot IDs.

        :param bot_ids: A set containing 3Commas Bot IDs.
        :return: A set containing 3Commas Bot Deal IDs.
        """
        deal_ids = set()
        for bot_id in bot_ids:
            try:
                time.sleep(THREE_COMMAS_API_INTERVAL_SECONDS)
                error, data = self.py3cw.request(
                    entity="bots",
                    action="show",
                    action_id=f"{bot_id}"
                )
                if error:
                    self.output_message(MessageType.ERROR, f"Failed to fetch bot info for bot id {bot_id}: {error}")
                    continue
                bot_name = data["name"]

                self.output_message(MessageType.INFO, f"Fetching active deal ids for bot '{bot_name}'")
                bot_deal_ids = set()
                completed = False
                offset = 0
                while not completed:
                    error, data = self.py3cw.request(
                        entity="deals",
                        action="",
                        payload={
                            "limit": THREE_COMMAS_DEALS_BATCH_SIZE,
                            "offset": offset,
                            "bot_id": bot_id,
                            "scope": "active"
                        }
                    )
                    if error:
                        self.output_message(
                            MessageType.ERROR,
                            f"Failed to fetch active deals for bot '{bot_name}': {error}"
                        )
                        completed = True  # Give up on this bot if we hit errors.
                    else:
                        for deal in data:
                            deal_id = deal["id"]
                            self.output_message(MessageType.DEBUG, f"Found active deal id {deal_id}")
                            bot_deal_ids.add(deal_id)
                        offset += len(data)  # Increase offset for next call.
                        completed = len(data) < THREE_COMMAS_DEALS_BATCH_SIZE  # Have we finished?
                self.output_message(MessageType.INFO, f"Found {len(bot_deal_ids)} active deals for bot '{bot_name}'")
                deal_ids.update(bot_deal_ids)
            except Exception as ex:
                self.output_message(MessageType.ERROR, f"Caught Exception fetching deal ids for bot id {bot_id}: {ex}")
        return deal_ids

    def _process_deal_ids(self, deal_ids: Set[int]):
        """
        Processes a specified collection of 3Commas Bot Deal IDs.

        :param deal_ids: A set containing 3Commas Bot Deal IDs.
        """
        for deal_id in deal_ids:
            try:
                time.sleep(THREE_COMMAS_API_INTERVAL_SECONDS)
                error, data = self.py3cw.request(
                    entity="deals",
                    action="show",
                    action_id=f"{deal_id}"
                )
                if error:
                    self.output_message(MessageType.ERROR, f"Failed to fetch deal info for deal id {deal_id}: {error}")
                    return

                # Apply profit-protection logic here.
                if self._deal_is_active(data):
                    self._apply_deal_profit_protection(data)
            except Exception as ex:
                self.output_message(MessageType.ERROR, f"Caught Exception processing deal id {deal_id}: {ex}")

    def _deal_is_active(self, deal: Dict):
        """
        Checks a deal to decide if it is active.

        :param deal: Dictionary containing the DCA Bot Deal information (fetched from 3Commas).
        :return: True if the deal is considered active, otherwise False.
        """
        deal_id = deal["id"]
        deal_status = deal["status"]
        if deal["finished?"]:
            self.output_message(MessageType.DEBUG, f"Ignoring finished deal id {deal_id}")
            return False
        if deal["status"] in [
            "cancelled",
            "completed",
            "failed",
            "panic_sell_pending",
            "panic_sell_order_placed",
            "panic_sold",
            "cancel_pending",
            "stop_loss_pending",
            "stop_loss_finished",
            "stop_loss_order_placed",
            "switched",
            "switched_take_profit",
            "liquidated",
            "bought_safety_pending",
            "bought_take_profit_pending",
            "settled"
        ]:
            self.output_message(MessageType.DEBUG, f"Ignoring deal id {deal_id} with status '{deal_status}'")
            return False
        return True

    def _apply_deal_profit_protection(self, deal: Dict):
        """
        Apply profit-protection to a DCA Bot Deal.

        :param deal: Dictionary containing the DCA Bot Deal information (fetched from 3Commas).
        """
        try:
            deal_id = deal["id"]
            deal_status = deal["status"]
            strategy = deal["strategy"]
            leverage_type = deal["leverage_type"]
            leverage_amount = 1.0
            if deal["leverage_custom_value"]:
                leverage_amount = float(deal["leverage_custom_value"])
            stop_loss_type = deal["stop_loss_type"]
            # Flip sign from 3Commas API convention for DCA Bot-Deals.
            stop_loss_percentage = -float(deal["stop_loss_percentage"])
            tsl_enabled = deal["tsl_enabled"]
            current_sl_is_loss = (stop_loss_type == "stop_loss") and (stop_loss_percentage < 0) and not tsl_enabled
            actual_profit_percentage = float(deal['actual_profit_percentage'])
            self.output_message(MessageType.INFO, f"Checking deal id {deal_id}")
            self.output_message(
                MessageType.INFO,
                ", ".join(
                    [
                        f"deal_id={deal_id}",
                        f"deal_status={deal_status}",
                        f"strategy={strategy}",
                        f"leverage_type={leverage_type}",
                        f"leverage_amount={leverage_amount}",
                        f"stop_loss_type={stop_loss_type}",
                        f"stop_loss_percentage={stop_loss_percentage}",
                        f"actual_profit_percentage={actual_profit_percentage}"
                    ]
                ),
                ", ".join(
                    [
                        f"deal_id={deal_id}",
                        f"deal_status={deal_status}",
                        f"strategy={strategy}",
                        f"leverage_type={leverage_type}",
                        f"leverage_amount={leverage_amount}",
                        f"stop_loss_type={stop_loss_type}",
                        f"stop_loss_percentage={self.markup_pnl_value(stop_loss_percentage)}",
                        f"actual_profit_percentage={self.markup_pnl_value(actual_profit_percentage)}"
                    ]
                )
            )
            # Evaluate deal to determine if StopLoss should be applied or updated.
            # TODO: Allow multiple PnL/SL pairs
            if current_sl_is_loss and (actual_profit_percentage >= self.target_pnl_percent):
                message = f"Deal id {deal_id} has reached {self.target_pnl_percent}% PnL, " + \
                          f"updating SL to {self.adjusted_sl_percent}%"
                console_message = \
                    f"Deal id {deal_id} has reached {self.markup_pnl_value(self.target_pnl_percent)}% PnL, " + \
                    f"updating SL to {self.markup_pnl_value(self.adjusted_sl_percent)}%"
                self.output_message(MessageType.INFO, message, console_message)
                self._send_telegram_message(message)
                # Update SL to self.adjusted_sl_percent.
                self._update_deal_stoploss(deal_id, self.adjusted_sl_percent)
            else:
                self.output_message(MessageType.INFO, f"Nothing to do for deal id {deal_id}")
        except Exception as ex:
            self.output_message(MessageType.ERROR, f"Caught Exception applying deal profit-protection: {ex}")

    def _update_deal_stoploss(self, deal_id, stop_loss_percentage: float) -> bool:
        """
        Updates the stoploss on a DCA Bot Deal.

        :param deal_id: The deal ID to be updated.
        :param stop_loss_percentage: The new stoploss percentage.
        :return: True if stoploss updated successfully, otherwise False.
        """
        try:
            # NOTE: DCA Bots on 3Commas use a flipped SL value.
            # i.e. a +ve SL on 3C means a true SL at a loss, and a -ve SL on 3C actually means a true SL in profit.
            error, data = self.py3cw.request(
                entity="deals",
                action="update_deal",
                action_id=f"{deal_id}",
                payload={
                    "deal_id": deal_id,
                    # "stop_loss_timeout_enabled": True,
                    # "stop_loss_timeout_in_seconds": 30,
                    "stop_loss_type": "stop_loss",
                    # Flip sign for 3Commas API convention for DCA Bot-Deals.
                    "stop_loss_percentage": -stop_loss_percentage
                }
            )
            if error:
                message = f"Failed to update SL for deal id {deal_id}: {error}"
                self.output_message(MessageType.ERROR, message)
                self._send_telegram_message(message)
                return False
            message = f"Updated SL for deal id {deal_id}"
            self.output_message(MessageType.SUCCESS, message)
            self._send_telegram_message(message)
            return True
        except Exception as ex:
            self.output_message(MessageType.ERROR, f"Caught Exception updating deal stoploss: {ex}")
            return False

    def _send_telegram_message(self, message: str):
        """
        Sends a message to user's Telegram, if configured.

        :param message: The message to be sent.
        """
        if "telegram" in self.config:
            telegram_config = self.config["telegram"]
            telegram_bot_token = telegram_config.get("telegram_bot_token", None)
            telegram_chat_id = telegram_config.get("telegram_chat_id", None)
            if telegram_bot_token and telegram_chat_id and message:
                url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage?" + \
                      f"chat_id={telegram_chat_id}&text={message}"
                requests.get(url)

    @staticmethod
    def output_message(message_type: MessageType, message: str, console_message: str = None):
        """
        Outputs a message to the console and/or logfile.

        :param message_type: Enum value indicating message level.
        :param message: Message to be output.
        :param console_message: Console-specific message (for rich formatting).
        """
        if message_type == MessageType.DEBUG:
            logger.debug(message)
        elif message_type == MessageType.INFO:
            rich.print(f"[black on blue]INFO[/black on blue]: {console_message or message}")
            logger.info(message)
        elif message_type == MessageType.SUCCESS:
            rich.print(f"[black on green]SUCCESS[/black on green]: {console_message or message}")
            logger.info(message)
        elif message_type == MessageType.WARNING:
            rich.print(f"[black on dark_orange3]WARNING[/black on dark_orange3]: {console_message or message}")
            logger.warning(message)
        elif message_type == MessageType.ERROR:
            rich.print(f"[black on red]ERROR[/black on red]: {console_message or message}")
            logger.error(message)

    @staticmethod
    def output_startup_message():
        """
        Outputs a startup message to the console and/or logfile.
        """
        message1 = f"BotNanny {__version__}"
        message2 = "Use at your own risk, no warranty supplied or implied!"
        message3 = "The authors and any contributors assume NO RESPONSIBILITY for your trading results."
        message4 = "If you find this program useful, please consider sending a small tip..."
        btc_address = "BTC: 3BvA3ft3F4maDnuy9z6jqAarZNsPSYU1CE"
        eth_address = "ETH: 0xb1d21907f05da3a30d890976a2423c43be0ae7d0"
        ltc_address = "LTC: MF6ET8pFEgV4TH83dt1qnwnSMPHbzQTbUj"

        BotNanny.output_message(MessageType.INFO, message1, f"[blue]{message1}[/blue]")
        BotNanny.output_message(MessageType.INFO, message2, f"[blue]{message2}[/blue]")
        BotNanny.output_message(MessageType.INFO, message3, f"[blue]{message3}[/blue]")
        BotNanny.output_message(MessageType.INFO, message4, f"[blue]{message4}[/blue]")
        BotNanny.output_message(MessageType.INFO, btc_address, f"[dark_orange]{btc_address}[/dark_orange]")
        BotNanny.output_message(MessageType.INFO, eth_address, f"[dark_orange]{eth_address}[/dark_orange]")
        BotNanny.output_message(MessageType.INFO, ltc_address, f"[dark_orange]{ltc_address}[/dark_orange]")

    @staticmethod
    def markup_pnl_value(pnl_value: float) -> str:
        """
        Applies rich-formatting to PnL values.

        :param pnl_value: The PnL value to be formatted.
        :return: Formatted string.
        """
        if pnl_value < 0:
            return f"[red]{pnl_value}[/red]"
        return f"[green]{pnl_value}[/green]"
