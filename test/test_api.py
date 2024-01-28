import json
from datetime import datetime
from unittest import TestCase

import pytz

from custom_components.yan_tibber_client.api.api import TibberApi, Statistics, LoadingLevel
from test.my_secrets import tibber_api_token


class TestTibberApi(TestCase):
    DEFAULT_TIME_ZONE = pytz.timezone('Europe/Berlin')  # pytz.timezone('US/Eastern')
    PERC_LOSS_LOAD_UNLOAD = 20

    @staticmethod
    def print_list(arr: []):
        for x in arr:
            print(x)

    def _get_today_tomorrow(self):
        api = TibberApi(tibber_api_token, self.PERC_LOSS_LOAD_UNLOAD, self.DEFAULT_TIME_ZONE)
        price_info = api.get_price_info()
        today = api.convert_to_list(price_info['today'])
        tomorrow = api.convert_to_list(price_info['tomorrow'])
        return api, today, tomorrow

    def test_get_price_data(self):
        api = TibberApi(tibber_api_token, self.PERC_LOSS_LOAD_UNLOAD, self.DEFAULT_TIME_ZONE)
        price_info = api.get_price_info()
        formatted_json = json.dumps(price_info, indent=2)
        print(formatted_json)

    # https://pypi.org/project/pytz/
    def test_timezone_handling(self):
        tibber_dt_str = '2024-01-27T00:00:00.000+01:00'
        tdt = datetime.fromisoformat(tibber_dt_str)
        now = datetime.now(self.DEFAULT_TIME_ZONE)
        self.assertTrue(tdt < now)

    def test_get_current_price(self):
        api = TibberApi(tibber_api_token, self.PERC_LOSS_LOAD_UNLOAD, self.DEFAULT_TIME_ZONE)
        price_info = api.get_price_info()
        current = api.convert_to_hourly(price_info['current'])
        print(current)

    def test_convert_to_list(self):
        api, today, tomorrow = self._get_today_tomorrow()
        TestTibberApi.print_list(today)
        TestTibberApi.print_list(tomorrow)

    def test_filter_future_items(self):
        api, today, tomorrow = self._get_today_tomorrow()

        x = today[0].starts_at
        now = datetime.now(self.DEFAULT_TIME_ZONE)
        self.assertTrue(x >= now or x < now)

        future = api.filter_future_items(today)
        future.extend(tomorrow)
        TestTibberApi.print_list(future)

    # https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.argrelextrema.html
    def test_relative_minima(self):
        api, today, tomorrow = self._get_today_tomorrow()
        values = api.relative_minima(today)
        TestTibberApi.print_list(values)

    def test_relative_maxima(self):
        api, today, tomorrow = self._get_today_tomorrow()
        values = api.relative_maxima(today)
        TestTibberApi.print_list(values)

    def test_relative_extrema(self):
        api, today, tomorrow = self._get_today_tomorrow()
        values = api.relative_extrema(today)
        TestTibberApi.print_list(values)

    def test_determine_loading_levels(self):
        api, today, tomorrow = self._get_today_tomorrow()
        future = api.filter_future_items(today)
        future.extend(tomorrow)
        # mark Min + Max
        api.mark_extrema(future)

        api.determine_loading_levels(future)
        TestTibberApi.print_list(future)

        future_load_from_net = api.filter_loading_level(future, LoadingLevel.LOAD_FROM_NET)
        print("future_load_from_net:")
        TestTibberApi.print_list(future_load_from_net)
        future_unload_battery = api.filter_loading_level(future, LoadingLevel.UNLOAD_BATTERY)
        print("future_unload_battery:")
        TestTibberApi.print_list(future_unload_battery)

    def test_merge_loading_level(self):
        api, today, tomorrow = self._get_today_tomorrow()
        api.determine_loading_levels(today)

        price_info = api.get_price_info()
        current = api.convert_to_hourly(price_info['current'])

        api.merge_loading_level(current, today)
        print(current)
        
    def test_statistics(self):
        api, today, tomorrow = self._get_today_tomorrow()
        stats_today = Statistics(today)
        print(stats_today)
