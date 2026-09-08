from __future__ import annotations

import datetime

import pytest

from mint.calendarutil import (
    add_business_days,
    add_months,
    business_days_between,
    days_in_month,
    end_of_month,
    is_business_day,
    month_series,
)
from mint.errors import Refused


class TestAddMonths:
    def test_a_plain_month_step(self):
        assert add_months(datetime.date(2026, 1, 15), 1) == datetime.date(2026, 2, 15)

    def test_the_thirty_first_clamps_to_february(self):
        assert add_months(datetime.date(2026, 1, 31), 1) == datetime.date(2026, 2, 28)

    def test_a_leap_february_takes_the_twenty_ninth(self):
        assert add_months(datetime.date(2028, 1, 31), 1) == datetime.date(2028, 2, 29)

    def test_it_rolls_across_the_year(self):
        assert add_months(datetime.date(2026, 11, 15), 3) == datetime.date(2027, 2, 15)

    def test_negative_months_go_backward(self):
        assert add_months(datetime.date(2026, 3, 15), -3) == datetime.date(2025, 12, 15)


class TestMonthSeries:
    def test_the_series_measures_from_the_original_day(self):
        # January 31 clamps in February but returns to 31 in March,
        # rather than sticking at 28 as repeated one-month steps would.
        series = month_series(datetime.date(2026, 1, 31), 3)
        assert series == [
            datetime.date(2026, 1, 31),
            datetime.date(2026, 2, 28),
            datetime.date(2026, 3, 31),
        ]

    def test_an_empty_series_is_refused(self):
        with pytest.raises(Refused):
            month_series(datetime.date(2026, 1, 1), 0)


class TestMonthEdges:
    def test_days_in_month(self):
        assert days_in_month(2026, 2) == 28
        assert days_in_month(2028, 2) == 29

    def test_end_of_month(self):
        assert end_of_month(datetime.date(2026, 2, 10)) == datetime.date(2026, 2, 28)


class TestBusinessDays:
    def test_weekends_are_not_business_days(self):
        assert not is_business_day(datetime.date(2026, 1, 3))  # Saturday
        assert is_business_day(datetime.date(2026, 1, 5))  # Monday

    def test_two_business_days_after_friday_is_tuesday(self):
        friday = datetime.date(2026, 1, 2)
        assert add_business_days(friday, 2) == datetime.date(2026, 1, 6)

    def test_a_holiday_is_skipped(self):
        friday = datetime.date(2026, 1, 2)
        holidays = frozenset({datetime.date(2026, 1, 5)})
        assert add_business_days(friday, 1, holidays) == datetime.date(2026, 1, 6)

    def test_counting_between_excludes_the_start(self):
        assert business_days_between(
            datetime.date(2026, 1, 2), datetime.date(2026, 1, 6)
        ) == 2

    def test_backward_counting_is_refused(self):
        with pytest.raises(Refused):
            add_business_days(datetime.date(2026, 1, 1), -1)
