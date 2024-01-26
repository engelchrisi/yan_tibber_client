from unittest import TestCase

from custom_components.yan_tibber_client.api.api import TibberApi
from test.my_secrets import tibber_api_token


class TestTibberApi(TestCase):

    @staticmethod
    def print_list(arr: []):
        for x in arr:
            print(x)

    @staticmethod
    def _get_today_tomorrow():
        api = TibberApi(tibber_api_token)
        price_info = api.get_price_info()
        today = api.convert_to_list(price_info['today'])
        tomorrow = api.convert_to_list(price_info['tomorrow'])
        return api, today, tomorrow

    def test_get_price_data(self):
        api = TibberApi(tibber_api_token)
        res = api.get_price_info()
        print(res)

    def test_convert_to_list(self):
        api, today, tomorrow = self._get_today_tomorrow()
        TestTibberApi.print_list(today)
        TestTibberApi.print_list(tomorrow)

    def test_filter_future_items(self):
        api, today, tomorrow = self._get_today_tomorrow()
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

    def test_find_values_in_distance(self):
        api, today, tomorrow = self._get_today_tomorrow()
        values = api.find_values_in_distance(5, 0.22, today)
        TestTibberApi.print_list(values)

    def test_blubber(self):
        api, today, tomorrow = self._get_today_tomorrow()
        total = today
        total.extend(tomorrow)
