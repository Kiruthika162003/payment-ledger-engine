from __future__ import annotations

import datetime

import pytest

from mint.card import CardReference, brand_for
from mint.errors import Refused

MARCH = datetime.date(2026, 3, 15)
MARCH_END = datetime.date(2026, 3, 31)
APRIL = datetime.date(2026, 4, 1)


def _card(**kwargs) -> CardReference:
    base = {
        "bin_digits": "424242",
        "last_four": "4242",
        "expiry_year": 2026,
        "expiry_month": 3,
    }
    base.update(kwargs)
    return CardReference(**base)


class TestBrand:
    def test_visa_from_a_leading_four(self):
        assert brand_for("424242") == "Visa"

    def test_mastercard_from_the_two_series(self):
        assert brand_for("222100") == "Mastercard"
        assert brand_for("510000") == "Mastercard"

    def test_amex_from_thirty_four(self):
        assert brand_for("340000") == "American Express"

    def test_an_unrecognized_range(self):
        assert brand_for("999999") == "Unknown"

    def test_a_non_numeric_range_is_refused(self):
        with pytest.raises(Refused):
            brand_for("42x2")


class TestMasking:
    def test_the_masked_form_shows_only_the_last_four(self):
        assert _card().masked() == "**** **** **** 4242"

    def test_the_description_reads_naturally(self):
        assert _card().describe() == "Visa ending 4242"

    def test_a_short_last_four_is_refused(self):
        with pytest.raises(Refused) as caught:
            _card(last_four="42")
        assert "mishandled" in str(caught.value)

    def test_a_non_numeric_last_four_is_refused(self):
        with pytest.raises(Refused):
            _card(last_four="42ab")


class TestExpiry:
    def test_a_card_is_valid_through_its_stated_month(self):
        card = _card()
        assert card.is_valid_on(MARCH)
        assert card.is_valid_on(MARCH_END)

    def test_it_declines_from_the_first_of_the_next_month(self):
        assert _card().is_expired(APRIL)

    def test_the_expiry_date_is_the_last_day(self):
        assert _card().expires_on() == datetime.date(2026, 3, 31)

    def test_a_february_expiry_lands_on_the_right_day(self):
        assert _card(expiry_month=2).expires_on() == datetime.date(2026, 2, 28)

    def test_months_until_expiry(self):
        assert _card(expiry_month=6).months_until_expiry(MARCH) == 3


class TestConstruction:
    def test_a_short_bin_is_refused(self):
        with pytest.raises(Refused):
            _card(bin_digits="4242")

    def test_an_impossible_month_is_refused(self):
        with pytest.raises(Refused):
            _card(expiry_month=13)

    def test_an_absurd_year_is_refused(self):
        with pytest.raises(Refused):
            _card(expiry_year=1900)
