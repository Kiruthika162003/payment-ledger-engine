from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused, StaleRate
from mint.fxrate import Rate, RateTable

JAN = datetime.date(2026, 1, 1)
JUN = datetime.date(2026, 6, 1)
MAR = datetime.date(2026, 3, 1)


class TestLookup:
    def test_a_direct_rate_is_returned(self):
        table = RateTable()
        table.add("USD", "EUR", Fraction(9, 10), JAN)
        assert table.rate_on("USD", "EUR", MAR) == Fraction(9, 10)

    def test_the_most_recent_rate_on_or_before_wins(self):
        table = RateTable()
        table.add("USD", "EUR", Fraction(9, 10), JAN)
        table.add("USD", "EUR", Fraction(95, 100), JUN)
        assert table.rate_on("USD", "EUR", MAR) == Fraction(9, 10)
        assert table.rate_on("USD", "EUR", JUN) == Fraction(95, 100)

    def test_a_future_rate_does_not_leak_backward(self):
        table = RateTable()
        table.add("USD", "EUR", Fraction(95, 100), JUN)
        with pytest.raises(StaleRate):
            table.rate_on("USD", "EUR", JAN)

    def test_the_inverse_is_used_when_the_direct_is_missing(self):
        table = RateTable()
        table.add("USD", "EUR", Fraction(9, 10), JAN)
        assert table.rate_on("EUR", "USD", MAR) == Fraction(10, 9)

    def test_a_pair_against_itself_is_one(self):
        assert RateTable().rate_on("USD", "USD", MAR) == Fraction(1)


class TestTriangulation:
    def test_a_thin_pair_prices_through_the_pivot(self):
        table = RateTable(pivot="USD")
        table.add("USD", "EUR", Fraction(9, 10), JAN)
        table.add("USD", "GBP", Fraction(8, 10), JAN)
        # EUR to GBP = (USD to GBP) / (USD to EUR) = 0.8 / 0.9
        assert table.rate_on("EUR", "GBP", MAR) == Fraction(10, 9) * Fraction(8, 10)

    def test_a_missing_path_is_refused_by_name(self):
        table = RateTable(pivot="USD")
        table.add("USD", "EUR", Fraction(9, 10), JAN)
        with pytest.raises(StaleRate) as caught:
            table.rate_on("EUR", "JPY", MAR)
        assert "EUR to JPY" in str(caught.value)


class TestRefusals:
    def test_a_nonpositive_rate_is_refused(self):
        with pytest.raises(Refused):
            RateTable().add("USD", "EUR", Fraction(0), JAN)

    def test_a_self_quote_is_refused(self):
        with pytest.raises(Refused):
            RateTable().add("USD", "USD", Fraction(1), JAN)

    def test_a_rate_inverts(self):
        rate = Rate("USD", "EUR", Fraction(9, 10), JAN)
        assert rate.inverse().ratio == Fraction(10, 9)
        assert rate.inverse().base == "EUR"
