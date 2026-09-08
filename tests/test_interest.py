from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.interest import (
    compound_interest,
    effective_annual_rate,
    future_value,
    simple_interest,
)
from mint.money import Money


class TestSimple:
    def test_a_full_year_at_ten_percent(self):
        interest = simple_interest(
            Money.of(1000, "USD"),
            Fraction(1, 10),
            datetime.date(2026, 1, 1),
            datetime.date(2027, 1, 1),
        )
        assert interest == Money.of(100, "USD")

    def test_half_a_year_is_half_the_interest(self):
        interest = simple_interest(
            Money.of(1000, "USD"),
            Fraction(1, 10),
            datetime.date(2026, 1, 1),
            datetime.date(2026, 1, 1) + datetime.timedelta(days=182),
        )
        # 1000 * 0.10 * 182/365, rounded.
        assert interest == Money.from_minor(4986, "USD")

    def test_a_negative_rate_is_refused(self):
        with pytest.raises(Refused):
            simple_interest(
                Money.of(1000, "USD"),
                Fraction(-1, 10),
                datetime.date(2026, 1, 1),
                datetime.date(2027, 1, 1),
            )


class TestCompound:
    def test_monthly_compounding_beats_simple(self):
        interest = compound_interest(Money.of(1000, "USD"), Fraction(12, 100), 12, 12)
        # 1000 * (1.01^12 - 1) = 126.83 rounded.
        assert interest == Money.from_minor(12683, "USD")

    def test_future_value_grows_the_principal(self):
        fv = future_value(Money.of(1000, "USD"), Fraction(12, 100), 12, 12)
        assert fv == Money.from_minor(112683, "USD")

    def test_the_effective_rate_exceeds_the_nominal(self):
        eff = effective_annual_rate(Fraction(12, 100), 12)
        assert eff > Fraction(12, 100)
        assert abs(float(eff) - 0.126825) < 1e-5

    def test_negative_periods_are_refused(self):
        with pytest.raises(Refused):
            compound_interest(Money.of(1000, "USD"), Fraction(1, 10), -1, 12)
