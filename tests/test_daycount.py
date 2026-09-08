from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.daycount import DayCount, year_fraction
from mint.errors import Refused


class TestConventions:
    def test_act_365_counts_real_days_over_365(self):
        f = year_fraction(
            datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), DayCount.ACT_365F
        )
        assert f == Fraction(30, 365)

    def test_act_360_uses_a_360_day_year(self):
        f = year_fraction(
            datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), DayCount.ACT_360
        )
        assert f == Fraction(30, 360)

    def test_thirty_360_makes_every_month_thirty(self):
        f = year_fraction(
            datetime.date(2026, 1, 31), datetime.date(2026, 2, 28), DayCount.THIRTY_360
        )
        # d1 clamps to 30; 30*(2-1) + (28-30) = 28 days.
        assert f == Fraction(28, 360)

    def test_thirty_360_handles_the_31_to_31_edge(self):
        f = year_fraction(
            datetime.date(2026, 1, 31), datetime.date(2026, 3, 31), DayCount.THIRTY_360
        )
        # both clamp to 30: 30*2 = 60 days.
        assert f == Fraction(60, 360)


class TestActAct:
    def test_within_a_non_leap_year(self):
        f = year_fraction(
            datetime.date(2026, 1, 1), datetime.date(2026, 7, 1), DayCount.ACT_ACT
        )
        assert f == Fraction((datetime.date(2026, 7, 1) - datetime.date(2026, 1, 1)).days, 365)

    def test_a_leap_year_uses_366(self):
        f = year_fraction(
            datetime.date(2028, 1, 1), datetime.date(2028, 7, 1), DayCount.ACT_ACT
        )
        assert f.denominator in (366, 183)

    def test_a_full_year_is_one(self):
        f = year_fraction(
            datetime.date(2026, 1, 1), datetime.date(2027, 1, 1), DayCount.ACT_ACT
        )
        assert f == Fraction(1)


class TestRefusals:
    def test_a_backward_period_is_refused(self):
        with pytest.raises(Refused):
            year_fraction(datetime.date(2026, 2, 1), datetime.date(2026, 1, 1))
