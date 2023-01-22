## Overview

BotNanny is a tool for monitoring and modifying 3Commas DCA Bot Deals.
Currently it can update the StopLoss of active deals once their PnL has reached a specified minimum value.


## Disclaimer

Use at your own risk. No warranty is supplied or implied.
The authors and any contributors assume NO RESPONSIBILITY for your trading results.


## Requirements

- Python >= 3.8
- pip
- 3Commas account


## Setup

Clone or extract the BotNanny project into a directory.

Change directory into the BotNanny directory.

[OPTIONAL] Create a new Python virtual environment: `python -m venv venv`

[OPTIONAL] Activate the new Python virtual environment: `source venv/bin/activate`

Install dependencies: `pip install -r requirements.txt`

Copy the example `config.toml` (found in the config directory): `cp ./config/config.toml ./config/live.toml`

Edit the file `config/live.toml` (found in the config directory) to provide the following:
- your 3Commas API key and secret
- 3Commas account IDs and/or bot IDs


## Usage

Change directory into the BotNanny directory.

Execute BotNanny: `python -m botnanny --config ./config/live.toml`

Processing activity should now be visible in the console and also in a logfile found in the logs directory.


## Support

Please create a github issue for any bugs and/or feature requests.

If you find this program useful, please consider sending a small tip...
- BTC: 3BvA3ft3F4maDnuy9z6jqAarZNsPSYU1CE
- ETH: 0xb1d21907f05da3a30d890976a2423c43be0ae7d0
- LTC: MF6ET8pFEgV4TH83dt1qnwnSMPHbzQTbUj
