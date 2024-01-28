"""Tibber API."""
from datetime import datetime, tzinfo
from enum import Enum
import logging

import numpy as np
import requests
from scipy.signal import argrelextrema

_LOGGER = logging.getLogger(__name__)


# https://community.home-assistant.io/t/tibber-sensor-for-future-price-tomorrow/253818/23
class PriceLevel(Enum):
    """Price level based on trailing price average (3 days for hourly values and 30 days for daily values)."""

    VERY_CHEAP = "VERY_CHEAP"
    """The price is smaller or equal to 60 % compared to average price."""
    CHEAP = "CHEAP"
    """The price is greater than 60 % and smaller or equal to 90 % compared to average price."""
    NORMAL = "NORMAL"
    """The price is greater than 90 % and smaller than 115 % compared to average price."""
    EXPENSIVE = "EXPENSIVE"
    """The price is greater or equal to 115 % and smaller than 140 % compared to average price."""
    VERY_EXPENSIVE = "VERY_EXPENSIVE"
    """The price is greater or equal to 140 % compared to average price."""

    @staticmethod
    def from_string(pl_str: str):  # noqa: D102
        mapping = {
            "VERY_CHEAP": PriceLevel.VERY_CHEAP,
            "CHEAP": PriceLevel.CHEAP,
            "NORMAL": PriceLevel.NORMAL,
            "EXPENSIVE": PriceLevel.EXPENSIVE,
            "VERY_EXPENSIVE": PriceLevel.VERY_EXPENSIVE,
        }

        return mapping.get(pl_str.upper())


class LoadingLevel(Enum):
    """The slots where loading and unloading makes sense as they have at least perc_loss_load_unload distance."""

    LOAD_FROM_NET = "LOAD_FROM_NET"
    """Loading from net makes sense as cheap enough."""
    UNLOAD_BATTERY = "UNLOAD_BATTERY"
    """Net is expensive thus battery unloading make sense."""


class ExtremaType(Enum):
    """Minimum or Maximum."""

    MIN = "MIN"
    """Absolute minimum."""
    REL_MIN = "REL_MIN"
    """Relative minimum."""
    REL_MAX = "REL_MAX"
    """Relative maximum."""
    MAX = "MAX"
    """Absolute maximum."""


class HourlyData:  # noqa: D101
    _level: PriceLevel
    _starts_at: datetime
    _price: float
    """Price in Cent/100*Kwh."""
    _loading_level: LoadingLevel
    _extrema_type: ExtremaType

    @property
    def level(self) -> PriceLevel:  # noqa: D102
        return self._level

    @property
    def starts_at(self) -> datetime:  # noqa: D102
        return self._starts_at

    @property
    def price(self) -> float:  # noqa: D102
        return self._price

    @property
    def loading_level(self) -> LoadingLevel:  # noqa: D102
        return self._loading_level

    @loading_level.setter
    def loading_level(self, value):
        self._loading_level = value

    @property
    def extrema_type(self) -> ExtremaType:  # noqa: D102
        return self._extrema_type

    @extrema_type.setter
    def extrema_type(self, value):
        self._extrema_type = value

    def __init__(self, level: PriceLevel, starts_at: datetime, price: float) -> None:  # noqa: D107
        self._level = level
        self._starts_at = starts_at
        self._price = price
        self._loading_level = None
        self._extrema_type = None

    def __str__(self) -> str:  # noqa: D105
        return f"HourlyLevel({self.level}, startsAt={self.starts_at}, {self.price} @/kWh, {self.loading_level}, {self.extrema_type})"


class Statistics:  # noqa: D101
    _start_time: datetime
    _end_time: datetime
    """Last time slot."""
    _avg_level: float  # PriceLevel
    _avg_price: float
    _min: HourlyData
    _max: HourlyData

    @property
    def start_time(self) -> datetime:  # noqa: D102
        return self._start_time

    @property
    def end_time(self) -> datetime:  # noqa: D102
        return self._end_time

    @property
    def avg_level(self) -> float:  # noqa: D102
        return self._avg_level

    @property
    def min(self) -> HourlyData:  # noqa: D102
        return self._min

    @property
    def avg_price(self) -> float:  # noqa: D102
        return self._avg_price

    @property
    def max(self) -> HourlyData:  # noqa: D102
        return self._max

    @staticmethod
    def _level_to_float(pl: PriceLevel) -> float:
        if pl == PriceLevel.VERY_CHEAP:
            return -2
        if pl == PriceLevel.CHEAP:
            return -1
        if pl == PriceLevel.NORMAL:
            return 0
        if pl == PriceLevel.EXPENSIVE:
            return 1
        if pl == PriceLevel.VERY_EXPENSIVE:
            return 2

    def __init__(self, arr: list[HourlyData]) -> None:  # noqa: D107
        self._start_time = arr[0].starts_at
        self._end_time = arr[len(arr) - 1].starts_at

        np_arr = TibberApi.get_prices_numpy(arr)
        self._avg_price = np.mean(np_arr)
        self._max = TibberApi.absolute_maximum(arr)
        self._min = TibberApi.absolute_minimum(arr)

        res = []
        for x in arr:
            res.append(self._level_to_float(x.level))
        np_arr = np.array(res)
        # TODO change to enum again
        self._avg_level = np.mean(np_arr)


class TibberApi:  # noqa: D101
    def __init__(  # noqa: D107
        self, token: str, perc_loss_load_unload: int, time_zone: tzinfo
    ) -> None:
        self._token = token
        self._perc_loss_load_unload = perc_loss_load_unload
        self._time_zone = time_zone

    @property
    def perc_loss_load_unload(self) -> int:
        """Percentag loss for loading + unloading."""
        return self._perc_loss_load_unload

    def get_price_info(self) -> []:  # noqa: D102
        headers = {
            "Accept-Language": "sv-SE",
            "User-Agent": "REST",
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": self._token,
        }
        url = "https://api.tibber.com/v1-beta/gql"
        payload = '{ "query": "{ viewer { homes { currentSubscription { priceInfo { current { total currency level } today { total startsAt level } tomorrow { total startsAt level }}}}}}" }'
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        if response.status_code == requests.codes.ok:
            data = response.json()
            return data["data"]["viewer"]["homes"][0]["currentSubscription"][
                "priceInfo"
            ]
        else:
            _LOGGER.error("Failed to get price data, %s", response.text)
            return []

    @staticmethod
    def convert_to_list(arr: []) -> list[HourlyData]:  # noqa: D102
        res: list[HourlyData] = []
        for x in arr:
            hl = HourlyData(
                PriceLevel.from_string(x["level"]),
                datetime.fromisoformat(x["startsAt"]),
                x["total"],
            )
            res.append(hl)
        return res

    @staticmethod
    def convert_to_hourly(current) -> HourlyData:  # noqa: D102
        res = HourlyData(
            PriceLevel.from_string(current["level"]),
            None,
            current["total"],
        )
        return res

    def filter_future_items(self, arr: list[HourlyData]) -> list[HourlyData]:
        """Filter out all items with startsAt <= now."""
        now = datetime.now(self._time_zone)

        filtered_values: list[HourlyData] = [x for x in arr if x.starts_at > now]
        return filtered_values

    @staticmethod
    def get_prices_numpy(arr: list[HourlyData]) -> np.array:  # noqa: D102
        res = []
        for x in arr:
            res.append(x.price)

        return np.array(res)

    @staticmethod
    def relative_minima(arr: list[HourlyData]) -> list[HourlyData]:  # noqa: D102
        data_array = TibberApi.get_prices_numpy(arr)
        extrema_indices = argrelextrema(data_array, np.less)[0]

        res: list[HourlyData] = []
        for x in extrema_indices:
            val = arr[x]
            val.extrema_type = ExtremaType.REL_MIN
            res.append(val)

        return res

    @staticmethod
    def relative_maxima(arr: list[HourlyData]) -> list[HourlyData]:  # noqa: D102
        data_array = TibberApi.get_prices_numpy(arr)
        extrema_indices = argrelextrema(data_array, np.greater)[0]

        res: list[HourlyData] = []
        for x in extrema_indices:
            val = arr[x]
            val.extrema_type = ExtremaType.REL_MAX
            res.append(val)

        return res

    @staticmethod
    def relative_extrema(arr: list[HourlyData]) -> list[HourlyData]:  # noqa: D102
        minima = TibberApi.relative_minima(arr)
        # determine absolute MIN
        min_x: HourlyData = None
        for x in minima:
            if min_x is None or x.price < min_x.price:
                min_x = x
        min_x.extrema_type = ExtremaType.MIN

        maxima = TibberApi.relative_maxima(arr)
        # determine absolute MAX
        max_x: HourlyData = None
        for x in maxima:
            if max_x is None or x.price > max_x.price:
                max_x = x
        max_x.extrema_type = ExtremaType.MAX

        extrema = minima
        extrema.extend(maxima)

        sorted_extrama = sorted(extrema, key=lambda x: x.starts_at)
        return sorted_extrama

    @staticmethod
    def mark_extrema(arr: list[HourlyData]) -> None:  # noqa: D102
        """Mark Min + Max."""
        TibberApi.absolute_minimum(arr)
        TibberApi.absolute_maximum(arr)

    @staticmethod
    def absolute_minimum(arr: list[HourlyData]) -> HourlyData:  # noqa: D102
        res: HourlyData = None
        for x in arr:
            if res is None or x.price < res.price:
                res = x

        if res is not None:
            res.extrema_type = ExtremaType.MIN
        return res

    @staticmethod
    def absolute_maximum(arr: list[HourlyData]) -> HourlyData:  # noqa: D102
        res: HourlyData = None
        for x in arr:
            if res is None or x.price > res.price:
                res = x

        if res is not None:
            res.extrema_type = ExtremaType.MAX
        return res

    def determine_loading_levels(self, arr: list[HourlyData]) -> None:
        """Mark all slots which are suitable for loading and unloading of the battery, which have at least perc_loss_load_unload distance."""
        factor = 1.0 + self.perc_loss_load_unload / 100

        for i in range(len(arr) - 1):
            hd1 = arr[i]
            # current slot is suitable for loading if there is a successor slot with price >= max_price
            max_price = hd1.price * factor
            found = False
            for j in range(i + 1, len(arr) - 1):
                hd2 = arr[j]
                if hd2.price >= max_price:
                    found = True
                    hd2.loading_level = LoadingLevel.UNLOAD_BATTERY

            if found:
                hd1.loading_level = LoadingLevel.LOAD_FROM_NET
