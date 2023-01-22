import argparse
import logging
import os
import sys
import tomli  # type: ignore

from logging.handlers import TimedRotatingFileHandler
from botnanny.botnanny import BotNanny
from . import __VERSION__

logger = logging.getLogger(__name__)


def main(args):
    """
    Main entry point.

    :param args: Command-line arguments.
    """
    # Parse command-line arguments.
    root_parser = argparse.ArgumentParser(prog="python3 -m botnanny")
    root_parser.add_argument("--logpath", type=str, help="path for log files", default="/var/log/botnanny")
    root_parser.add_argument("--config", type=str, help="config file", required=True)
    root_parser.add_argument("-v", "--version", action="version", version=f"BotNanny {__VERSION__}")

    args.pop(0)  # Remove __main__.py from start of args.
    args = root_parser.parse_args(args)

    # Configure logging.
    os.makedirs(args.logpath, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            TimedRotatingFileHandler(os.path.join(args.logpath, "botnanny.log"), when="midnight", utc=True)
        ]
    )

    # Read config file.
    config = read_config(args.config)

    botnanny = BotNanny(config)
    botnanny.run()


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
