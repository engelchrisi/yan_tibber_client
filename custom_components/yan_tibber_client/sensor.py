"""All Sensors."""
from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .api import TibberApi
from .const import PRICE_SENSOR_NAME

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        # vol.Optional(CONF_DAILY_USAGE, default=True): cv.boolean,
        # vol.Optional(CONF_USAGE_DAYS, default=10): cv.positive_int,
        # vol.Optional(CONF_DATE_FORMAT, default="%b %d %Y"): cv.string,
    }
)

SCAN_INTERVAL = timedelta(minutes=60)


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
):  # noqa: D103
    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)

    api = TibberApi(email, password)

    _LOGGER.debug("Setting up sensor(s)")

    sensors = []
    sensors.append(TibberPricesSensor(api))
    async_add_entities(sensors, True)


class TibberPricesSensor(Entity):  # noqa: D101
    def __init__(self, api) -> None:  # noqa: D107
        self._name = PRICE_SENSOR_NAME
        self._icon = "mdi:account-cash"
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

    def update(self):
        """Update state and attributes."""
        _LOGGER.debug("Checking jwt validity")
        if self._api.check_auth():
            data = self._api.get_price_data()
            if data:
                firstKey = next(iter(data))
                value = data[firstKey]["cost_in_kr"] if data[firstKey] else 0
                self._state_attributes["current_month"] = value
            spot_price_data = self._api.get_spot_price()
            if spot_price_data:
                _LOGGER.debug("Fetching daily prices")
                today = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                todaysData = []
                tomorrowsData = []
                yesterdaysData = []
                for d in spot_price_data["data"]:
                    timestamp = datetime.strptime(
                        spot_price_data["data"][d]["localtime"], "%Y-%m-%d %H:%M"
                    )
                    if timestamp.date() == today.date():
                        if spot_price_data["data"][d]["price"] is not None:
                            todaysData.append(self.make_attribute(spot_price_data, d))
                    elif timestamp.date() == (today.date() + timedelta(days=1)):
                        if spot_price_data["data"][d]["price"] is not None:
                            tomorrowsData.append(
                                self.make_attribute(spot_price_data, d)
                            )
                    elif timestamp.date() == (today.date() - timedelta(days=1)):
                        if spot_price_data["data"][d]["price"] is not None:
                            yesterdaysData.append(
                                self.make_attribute(spot_price_data, d)
                            )
                self._state_attributes["current_day"] = todaysData
                self._state_attributes["next_day"] = tomorrowsData
                self._state_attributes["previous_day"] = yesterdaysData
        else:
            _LOGGER.error("Unable to log in!")

    def make_attribute(self, response, value):  # noqa: D102
        if response:
            newPoint = {}
            today = datetime.now()
            price = response["data"][value]["price"]
            dt_object = datetime.strptime(
                response["data"][value]["localtime"], "%Y-%m-%d %H:%M"
            )
            newPoint["date"] = dt_object.strftime(self._date_format)
            newPoint["time"] = dt_object.strftime(self._time_format)
            if price is not None:
                rounded = self.format_price(price)
                newPoint["price"] = rounded
                if dt_object.hour == today.hour and dt_object.day == today.day:
                    self._state = rounded
            else:
                newPoint["price"] = 0
            return newPoint

    def format_price(self, price):  # noqa: D102
        return round(((price / 1000) / 100), 4)

    def make_data_attribute(self, name, response, nameOfPriceAttr):  # noqa: D102
        if response:
            points = response.get("points", None)
            data = []
            for point in points:
                price = point[nameOfPriceAttr]
                if price is not None:
                    newPoint = {}
                    dt_object = datetime.utcfromtimestamp(point["timestamp"])
                    newPoint["date"] = dt_object.strftime(self._date_format)
                    newPoint["time"] = dt_object.strftime(self._time_format)
                    newPoint["price"] = str(price / 100)
                    data.append(newPoint)
            self._state_attributes[name] = data
