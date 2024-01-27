"""All Sensors."""
import logging
from datetime import datetime, timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .api.api import ExtremaType, HourlyData, LoadingLevel, Statistics, TibberApi
from .const import PRICE_SENSOR_NAME

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        # vol.Optional(CONF_DAILY_USAGE, default=True): cv.boolean,
        # vol.Optional(CONF_USAGE_DAYS, default=10): cv.positive_int,
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

    api = TibberApi(token, dt_util.DEFAULT_TIME_ZONE)

    _LOGGER.debug("Setting up sensor(s)")

    sensors = []
    sensors.append(TibberPricesSensor(api))
    async_add_entities(sensors, True)


class TibberPricesSensor(Entity):  # noqa: D101
    _current: HourlyData
    _today: list[HourlyData]
    _stats_today: Statistics
    _tomorrow: list[HourlyData]
    _stats_tomorrow: Statistics
    _future: list[HourlyData]
    _stats_future: Statistics

    def __init__(self, api: TibberApi) -> None:  # noqa: D107
        self._name = PRICE_SENSOR_NAME
        self._icon = "mdi:currency-eur"
        self._state = 0
        self._state_attributes = {}
        self._unit_of_measurement = "Cent/kWh"
        self._api = api

        self._current = None
        self._today = []
        self._stats_today = None
        self._tomorrow = []
        self._stats_tomorrow = None
        self._future = []
        self._stats_future = None

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
        if x.loading_level is not LoadingLevel.UNKNOWN:
            res["loading_level"] = x.loading_level
        if x.extrema_type is not ExtremaType.NONE:
            res["extrema_type"] = x.extrema_type

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
            "min": TibberPricesSensor.hourly_data_to_json(x.min),
            "avg_price": TibberPricesSensor._format_price(x.avg_price),
            "max": TibberPricesSensor.hourly_data_to_json(x.max),
        }
        return res

    def update(self):
        """Update state and attributes."""
        _LOGGER.debug("Start TibberPricesSensor.update")
        api = self._api
        now = datetime.now(dt_util.DEFAULT_TIME_ZONE)
        price_info = api.get_price_info()

        self._current = api.convert_to_hourly(price_info["current"])
        self._state = TibberPricesSensor._format_price(self._current.price)

        self._today = api.convert_to_list(price_info["today"])
        self._stats_today = Statistics(self._today)

        self._tomorrow = api.convert_to_list(price_info["tomorrow"])
        # tomorrow value appears around 12:00
        if self._tomorrow is not None and len(self._tomorrow) > 0:
            self._stats_tomorrow = Statistics(self._tomorrow)
        else:
            self._stats_tomorrow = None

        self._future = api.filter_future_items(self._today)
        self._future.extend(self._tomorrow)
        self._stats_future = Statistics(self._future)

        self._state_attributes["last_update"] = TibberPricesSensor._format_date(now)
        self._state_attributes["current"] = TibberPricesSensor.hourly_data_to_json(self._current)

        self._state_attributes["sep1"] = "========================================"
        self._state_attributes["today_stats"] = self._statistics_to_json(self._stats_today)
        self._state_attributes["today"] = self.convert_to_json_list(self._today)

        # tomorrow value appears around 12:00
        self._state_attributes["sep2"] = "========================================"
        if self._tomorrow is not None and len(self._tomorrow) > 0:
            self._state_attributes["tomorrow_stats"] = self._statistics_to_json(self._stats_tomorrow)
            self._state_attributes["tomorrow"] = self.convert_to_json_list(self._tomorrow)
        else:
            self._state_attributes["stats_tomorrow"] = None
            self._state_attributes["tomorrow"] = []

        self._state_attributes["sep3"] = "========================================"
        self._state_attributes["future_stats"] = self._statistics_to_json(
            self._stats_future
        )
        self._state_attributes["future"] = self.convert_to_json_list(self._future)
        _LOGGER.debug("EOF TibberPricesSensor.update")
