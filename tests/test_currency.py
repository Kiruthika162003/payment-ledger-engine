from __future__ import annotations

import pytest

from mint import currency
from mint.errors import UnknownCurrency


class TestExponents:
    def test_dollar_splits_into_hundredths(self):
        assert currency.get("USD").minor_per_major() == 100

    def test_yen_has_no_minor_unit(self):
        assert currency.get("JPY").exponent == 0
        assert currency.get("JPY").minor_per_major() == 1

    def test_dinar_splits_into_thousandths(self):
        assert currency.get("BHD").exponent == 3
        assert currency.get("BHD").minor_per_major() == 1000


class TestLookup:
    def test_codes_are_case_insensitive(self):
        assert currency.get("usd").code == "USD"

    def test_an_unknown_code_is_refused_by_name(self):
        with pytest.raises(UnknownCurrency) as caught:
            currency.get("XYZ")
        assert "XYZ" in str(caught.value)

    def test_is_known_reports_membership(self):
        assert currency.is_known("EUR")
        assert not currency.is_known("XYZ")


class TestCashRounding:
    def test_the_swiss_franc_rounds_cash_to_five_centimes(self):
        assert currency.get("CHF").cash_increment == 5

    def test_most_currencies_round_cash_to_the_minor_unit(self):
        assert currency.get("USD").cash_increment == 1


class TestRegistry:
    def test_all_codes_are_sorted(self):
        codes = currency.all_codes()
        assert codes == sorted(codes)
        assert "USD" in codes
