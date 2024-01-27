"""Constants."""
from typing import Final

NAME: Final = "Yet another Tibber Client"
DOMAIN: Final = "yan_tibber_client"
VERSION: Final = "0.1.0"
DEPOT_URL: Final = "https://github.com/engelchrisi/yan_tibber_client"
ISSUE_URL: Final = "https://github.com/engelchrisi/yan_tibber_client/issues"

STARTUP_MESSAGE: Final = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
Clone this depot to adapt your own SMA device:
{DEPOT_URL}
-------------------------------------------------------------------
"""

PRICE_SENSOR_NAME: Final = "Tibber Prices"
CONF_LOAD_UNLOAD_LOSS_PERC: Final = "perc_loss_load_unload"
