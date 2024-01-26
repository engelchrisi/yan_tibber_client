"""Tibber API."""
import logging
from datetime import datetime
from enum import Enum
from typing import List

import numpy as np
import requests
from scipy.signal import argrelextrema

_LOGGER = logging.getLogger(__name__)


# https://community.home-assistant.io/t/tibber-sensor-for-future-price-tomorrow/253818/23
class PriceLevel(Enum):
    """Price level based on trailing price average (3 days for hourly values and 30 days for daily values)"""
    """The price is greater than 60 % and smaller or equal to 90 % compared to average price."""
    VERY_CHEAP = -2
    CHEAP = -1
    """The price is smaller or equal to 60 % compared to average price."""
    NORMAL = 0
    """The price is greater than 90 % and smaller than 115 % compared to average price."""
    EXPENSIVE = 1
    """The price is greater or equal to 115 % and smaller than 140 % compared to average price."""
    VERY_EXPENSIVE = 1
    """The price is greater or equal to 140 % compared to average price."""

    @staticmethod
    def from_string(pl_str: str):
        mapping = {
            'VERY_CHEAP': PriceLevel.VERY_CHEAP,
            'CHEAP': PriceLevel.CHEAP,
            'NORMAL': PriceLevel.NORMAL,
            'EXPENSIVE': PriceLevel.EXPENSIVE,
            'VERY_EXPENSIVE': PriceLevel.VERY_EXPENSIVE,
        }

        return mapping.get(pl_str.upper())


class LoadingLevel(Enum):
    """The price is greater than 60 % and smaller or equal to 90 % compared to average price."""
    UNKNOWN = 0
    """Not determined yet."""
    UNSPECTACULAR = 1
    """Not expensive nor cheap."""
    LOAD_FROM_NET = 2
    """Loading from net makes sense as cheap enough."""
    UNLOAD_BATTERY = 3
    """Net is expensive thus battery unloading make sense."""


class ExtremaType(Enum):
    """Minimum or Maximum."""
    NONE = 0
    """Not minimum nor maximum."""
    MIN = 1
    """Absolute minimum."""
    REL_MIN = 2
    """Relative minimum."""
    REL_MAX = 3
    """Relative maximum."""
    MAX = 4
    """Absolute maximum."""


class HourlyLevel():
    _level: PriceLevel
    _starts_at: datetime
    _price: float
    _loading_level: LoadingLevel
    _extrema_type: ExtremaType

    @property
    def level(self) -> PriceLevel:
        return self._level

    @property
    def starts_at(self) -> datetime:
        return self._starts_at

    @property
    def price(self) -> float:
        return self._price

    @property
    def loading_level(self) -> LoadingLevel:
        return self._loading_level

    @loading_level.setter
    def loading_level(self, value):
        self._loading_level = value

    @property
    def extrema_type(self) -> ExtremaType:
        return self._extrema_type

    @extrema_type.setter
    def extrema_type(self, value):
        self._extrema_type = value

    def __init__(self, level: PriceLevel, starts_at: datetime, price: float) -> None:  # noqa: D107
        self._level = level
        self._starts_at = starts_at.replace(tzinfo=None)
        self._price = price
        self._loading_level = LoadingLevel.UNKNOWN
        self._extrema_type = ExtremaType.NONE

    def __str__(self) -> str:
        return f"HourlyLevel({self.level}, startsAt={self.starts_at}, {self.price}€, {self.loading_level}, {self.extrema_type})"


class TibberApi:  # noqa: D101
    def __init__(self, token) -> None:  # noqa: D107
        self._token = token

    def get_price_info(self) -> []:
        headers = {'Accept-Language': 'sv-SE',
                   'User-Agent': 'REST',
                   'Content-Type': 'application/json; charset=utf-8',
                   'Authorization': self._token}
        url = 'https://api.tibber.com/v1-beta/gql'
        payload = '{ "query": "{ viewer { homes { currentSubscription { priceInfo { current { total currency level } today { total startsAt level } tomorrow { total startsAt level }}}}}}" }'
        response = requests.post(url, headers=headers, data=payload)
        if response.status_code == requests.codes.ok:
            data = response.json()
            return data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
        else:
            _LOGGER.error("Failed to get price data, %s", response.text)
            return []

    @staticmethod
    def convert_to_list(arr: []) -> List[HourlyLevel]:
        res: List[HourlyLevel] = []
        for x in arr:
            hl = HourlyLevel(PriceLevel.from_string(x['level']), datetime.fromisoformat(x['startsAt']), x['total'])
            res.append(hl)
        return res

    @staticmethod
    def filter_future_items(arr: List[HourlyLevel]) -> List[HourlyLevel]:
        """Filter out all items with startsAt <= now."""
        now = datetime.now()

        filtered_values: List[HourlyLevel] = [x for x in arr if x.starts_at > now]
        return filtered_values

    @staticmethod
    def _get_prices_numpy(arr: List[HourlyLevel]) -> np.array:
        res = []
        for x in arr:
            res.append(x.price)

        return np.array(res)

    @staticmethod
    def relative_minima(arr: List[HourlyLevel]) -> List[HourlyLevel]:
        data_array = TibberApi._get_prices_numpy(arr)
        extrema_indices = argrelextrema(data_array, np.less)[0]

        res: List[HourlyLevel] = []
        for x in extrema_indices:
            val = arr[x]
            val.extrema_type = ExtremaType.REL_MIN
            res.append(val)

        return res

    @staticmethod
    def relative_maxima(arr: List[HourlyLevel]) -> List[HourlyLevel]:
        data_array = TibberApi._get_prices_numpy(arr)
        extrema_indices = argrelextrema(data_array, np.greater)[0]

        res: List[HourlyLevel] = []
        for x in extrema_indices:
            val = arr[x]
            val.extrema_type = ExtremaType.REL_MAX
            res.append(val)

        return res

    @staticmethod
    def relative_extrema(arr: List[HourlyLevel]) -> List[HourlyLevel]:
        minima = TibberApi.relative_minima(arr)
        # determine absolute MIN
        min_x: HourlyLevel = None
        for x in minima:
            if min_x is None or x.price < min_x.price:
                min_x = x
        min_x.extrema_type = ExtremaType.MIN

        maxima = TibberApi.relative_maxima(arr)
        # determine absolute MAX
        max_x: HourlyLevel = None
        for x in maxima:
            if max_x is None or x.price > max_x.price:
                max_x = x
        max_x.extrema_type = ExtremaType.MAX

        extrema = minima
        extrema.extend(maxima)

        sorted_extrama = sorted(extrema, key=lambda x: x.starts_at)
        return sorted_extrama

    @staticmethod
    def absolute_minimum(arr: List[HourlyLevel]) -> float:
        res: float = 99
        for x in arr:
            if x.price < res:
                res = x.price

        res.extrema_type = ExtremaType.MIN
        return res

    @staticmethod
    def absolute_maximum(arr: List[HourlyLevel]) -> float:
        res: float = 0
        for x in arr:
            if x.price > res:
                res = x.price

        return res

    @staticmethod
    def find_values_in_distance(delta_perc: int, min_max_val: float, arr: List[HourlyLevel]) -> List[HourlyLevel]:
        """Return all hourly level values that are at maximum delta_perc % distance to a max or min value."""
        res: List[HourlyLevel] = []
        max_distance = abs(min_max_val * float(delta_perc) / 100)

        for x in arr:
            if abs(x.price - min_max_val) <= max_distance:
                res.append(x)
        return res
