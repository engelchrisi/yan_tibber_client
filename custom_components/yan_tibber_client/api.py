"""Tibber API."""
import logging

import pyTibber

_LOGGER = logging.getLogger(__name__)


class TibberApi:  # noqa: D101
    def __init__(self, email, password) -> None:  # noqa: D107
        self._email = email
        self._password = password

    # def get_price_data(self):
    #     today = datetime.today()
    #     start = "?from=" + str(today.year) + "-" + today.strftime("%m") + "-01"
    #     endOfMonth = calendar.monthrange(today.year, today.month)[1]
    #     end = (
    #         "&to="
    #         + str(today.year)
    #         + "-"
    #         + today.strftime("%m")
    #         + "-"
    #         + str(endOfMonth)
    #     )
    #     url = (
    #         self._url_facilities_base
    #         + self._facility_id
    #         + "/consumption-cost"
    #         + start
    #         + end
    #         + "&resolution=monthly&prediction=false&exclude_additions=false&exclude_monthly_fee=false&exclude_vat=false"
    #     )
    #     response = requests.get(url, headers=self._headers)
    #     data = {}
    #     if response.status_code == requests.codes.ok:
    #         data = response.json()
    #         return data["data"]
    #     else:
    #         _LOGGER.error("Failed to get price data, %s", response.text)
    #         return data
