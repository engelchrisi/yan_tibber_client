"""All Sensors."""
from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .api.api import HourlyData, LoadingLevel, Statistics, TibberApi
from .const import CONF_LOAD_UNLOAD_LOSS_PERC, PRICE_SENSOR_NAME

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_LOAD_UNLOAD_LOSS_PERC, default=20): cv.positive_int,
        # vol.Optional(CONF_DAILY_USAGE, default=True): cv.boolean,
        # vol.Optional(CONF_DATE_FORMAT, default="%b %d %Y"): cv.string,
    }
)

# You can control the polling interval for your integration by defining a SCAN_INTERVAL constant in your platform.
SCAN_INTERVAL = timedelta(minutes=30)


async def async_setup_platform(  # noqa: D103
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    token = config.get(CONF_TOKEN)
    perc_loss_load_unload = config.get(CONF_LOAD_UNLOAD_LOSS_PERC)
    api = TibberApi(token, perc_loss_load_unload, dt_util.DEFAULT_TIME_ZONE)

    _LOGGER.debug("Setting up sensor(s)")

    sensors = [TibberPricesSensor(api)]
    async_add_entities(sensors, True)


class TibberPricesSensor(Entity):  # noqa: D101
    def __init__(self, api: TibberApi) -> None:  # noqa: D107
        self._name = PRICE_SENSOR_NAME
        self._icon = "mdi:currency-eur"
        self._state = 0
        self._state_attributes = {}
        self._unit_of_measurement = "Cent/kWh"
        self._api = api

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._state_attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @staticmethod
    def hourly_data_to_json(x: HourlyData) -> {}:  # noqa: D102
        res = {
            "level": x.level.value,
            "price": TibberPricesSensor._format_price(x.price),
        }
        if x.starts_at is not None:
            res["starts_at"] = TibberPricesSensor._format_date(x.starts_at)
        if x.loading_level is not None:
            res["loading_level"] = x.loading_level.value
        if x.extrema_type is not None:
            res["extrema_type"] = x.extrema_type.value

        return res

    @staticmethod
    def convert_to_json_list(arr: list[HourlyData]) -> []:  # noqa: D102
        res = []
        for x in arr:
            res.append(TibberPricesSensor.hourly_data_to_json(x))
        return res

    @staticmethod
    def _format_price(price: float) -> float:
        """Return rounded price in Cent / kWh."""
        return round(price * 100, 1)

    @staticmethod
    def _format_date(dt: datetime) -> str:
        local_timestamp = dt_util.as_local(dt)
        return local_timestamp.isoformat()

    @staticmethod
    def _statistics_to_json(x: Statistics) -> {}:  # noqa: D102
        res = {
            "start_time": TibberPricesSensor._format_date(x.start_time),
            "end_time": TibberPricesSensor._format_date(x.end_time),
            "avg_level": x.avg_level.value,
            "min": TibberPricesSensor.hourly_data_to_json(x.min),
            "avg_price": TibberPricesSensor._format_price(x.avg_price),
            "max": TibberPricesSensor.hourly_data_to_json(x.max),
        }
        return res

    def update(self):
        """Update state and attributes."""
        _LOGGER.debug("Start update")
        api = self._api
        now = datetime.now(dt_util.DEFAULT_TIME_ZONE)
        price_info = api.get_price_info()
        _LOGGER.debug("Finished rest call")

        current = api.convert_to_hourly(price_info["current"])
        self._state = TibberPricesSensor._format_price(current.price)

        today = api.convert_to_list(price_info["today"])
        api.mark_extrema(today)
        stats_today = Statistics(today)
        api.determine_loading_levels(today)
        # take over corresponding loading level from today array
        api.merge_loading_level(current, today)

        today_load_from_net = api.filter_loading_level(
            today, LoadingLevel.LOAD_FROM_NET
        )
        today_unload_battery = api.filter_loading_level(
            today, LoadingLevel.UNLOAD_BATTERY
        )

        tomorrow = api.convert_to_list(price_info["tomorrow"])
        api.mark_extrema(tomorrow)
        # tomorrow value appears around 12:00
        if tomorrow is not None and len(tomorrow) > 0:
            stats_tomorrow = Statistics(tomorrow)
            api.determine_loading_levels(tomorrow)
            tomorrow_load_from_net = api.filter_loading_level(
                tomorrow, LoadingLevel.LOAD_FROM_NET
            )
            tomorrow_unload_battery = api.filter_loading_level(
                tomorrow, LoadingLevel.UNLOAD_BATTERY
            )
        else:
            stats_tomorrow = None
            tomorrow_load_from_net = []
            tomorrow_unload_battery = []

        future = api.filter_future_items(today)
        future.extend(tomorrow)
        api.mark_extrema(future)
        stats_future = Statistics(future)

        ######################################################
        # Prepare sensor attributes

        self._state_attributes["last_update"] = TibberPricesSensor._format_date(now)
        self._state_attributes["current"] = TibberPricesSensor.hourly_data_to_json(
            current
        )

        self._state_attributes["sep1"] = "========================================"
        self._state_attributes["today_stats"] = self._statistics_to_json(stats_today)
        self._state_attributes["today"] = self.convert_to_json_list(today)
        self._state_attributes["today_load_from_net"] = self.convert_to_json_list(
            today_load_from_net
        )
        self._state_attributes["today_unload_battery"] = self.convert_to_json_list(
            today_unload_battery
        )

        # tomorrow value appears around 12:00
        self._state_attributes["sep2"] = "========================================"
        if tomorrow is not None and len(tomorrow) > 0:
            self._state_attributes["tomorrow_stats"] = self._statistics_to_json(
                stats_tomorrow
            )
            self._state_attributes["tomorrow"] = self.convert_to_json_list(tomorrow)
            self._state_attributes[
                "tomorrow_load_from_net"
            ] = self.convert_to_json_list(tomorrow_load_from_net)
            self._state_attributes[
                "tomorrow_unload_battery"
            ] = self.convert_to_json_list(tomorrow_unload_battery)
        else:
            self._state_attributes["stats_tomorrow"] = None
            self._state_attributes["tomorrow"] = []

        self._state_attributes["sep3"] = "========================================"
        self._state_attributes["future_stats"] = self._statistics_to_json(stats_future)
        self._state_attributes["future"] = self.convert_to_json_list(future)
        _LOGGER.debug("EOF update")
