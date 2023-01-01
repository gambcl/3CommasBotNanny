import argparse
import logging
import os
import sys
import tomli  # type: ignore

from bot_nanny.bot_nanny import BotNanny
from . import __version__

logger = logging.getLogger(__name__)


def main(args):
    """
    Main entry point.

    :param args: Command-line arguments.
    """
    # Parse command-line arguments.
    root_parser = argparse.ArgumentParser(prog="python3 -m lunar_research")
    root_parser.add_argument("--config", type=str, help="config file", required=True)
    root_parser.add_argument("-v", "--version", action="version", version=f"BotNanny {__version__}")

    args.pop(0)  # Remove __main__.py from start of args.
    args = root_parser.parse_args(args)

    # Configure logging.
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        filename=os.path.join("logs", f"bot_nanny.{os.getpid()}.log"),
        filemode="w",
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        level=logging.DEBUG)

    # Read config file.
    config = read_config(args.config)

    bot_nanny = BotNanny(config)
    bot_nanny.run()


def read_config(filepath: str):
    """
    Reads a TOML config file.

    :param filepath: The location of the config file.
    :return: A dictionary representation of the TOML config file.
    """
    try:
        logger.debug(f"Reading config file: {filepath}")
        with open(filepath, "rb") as file:
            config_toml = tomli.load(file)
            return config_toml
    except OSError:
        logger.exception(f"Failed to read config file: {filepath}")
        return None


if __name__ == '__main__':
    main(sys.argv)