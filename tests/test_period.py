from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.period import AccountingPeriod, PeriodCalendar, PeriodStatus

JAN = datetime.date(2026, 1, 1)


def _calendar() -> PeriodCalendar:
    calendar = PeriodCalendar()
    calendar.add_months_from(JAN, 3)
    return calendar


class TestCalendar:
    def test_months_tile_the_calendar(self):
        calendar = _calendar()
        assert [p.name for p in calendar.periods] == ["2026-01", "2026-02", "2026-03"]
        assert calendar.gaps() == []

    def test_the_period_for_a_date(self):
        calendar = _calendar()
        assert calendar.period_for(datetime.date(2026, 2, 14)).name == "2026-02"

    def test_a_date_outside_every_period_is_refused(self):
        with pytest.raises(Refused) as caught:
            _calendar().period_for(datetime.date(2026, 7, 1))
        assert "no rule to follow" in str(caught.value)

    def test_an_overlapping_period_is_refused(self):
        calendar = _calendar()
        with pytest.raises(Refused) as caught:
            calendar.add(
                AccountingPeriod("dup", datetime.date(2026, 1, 15), datetime.date(2026, 2, 5))
            )
        assert "contradictory rules" in str(caught.value)

    def test_a_gap_is_reported(self):
        calendar = PeriodCalendar()
        calendar.add(AccountingPeriod("a", JAN, datetime.date(2026, 1, 31)))
        calendar.add(
            AccountingPeriod("c", datetime.date(2026, 3, 1), datetime.date(2026, 3, 31))
        )
        assert calendar.gaps() == [
            (datetime.date(2026, 2, 1), datetime.date(2026, 2, 28))
        ]


class TestGuard:
    def test_an_open_period_accepts_postings(self):
        calendar = _calendar()
        assert calendar.guard_posting(datetime.date(2026, 1, 5)).name == "2026-01"

    def test_a_closed_period_refuses_a_backdated_entry(self):
        calendar = _calendar()
        calendar.close("2026-01")
        with pytest.raises(Refused) as caught:
            calendar.guard_posting(datetime.date(2026, 1, 5))
        assert "already been reported" in str(caught.value)

    def test_reopening_lets_postings_through_again(self):
        calendar = _calendar()
        calendar.close("2026-01")
        calendar.reopen("2026-01")
        assert calendar.guard_posting(datetime.date(2026, 1, 5)).name == "2026-01"


class TestLocking:
    def test_a_locked_period_cannot_be_reopened(self):
        calendar = _calendar()
        calendar.lock("2026-01")
        with pytest.raises(Refused) as caught:
            calendar.reopen("2026-01")
        assert "no longer ours to revise" in str(caught.value)

    def test_a_locked_period_cannot_be_closed_again(self):
        calendar = _calendar()
        calendar.lock("2026-01")
        with pytest.raises(Refused):
            calendar.close("2026-01")

    def test_an_unknown_period_name_is_refused(self):
        with pytest.raises(Refused):
            _calendar().by_name("2099-01")

    def test_a_backward_period_is_refused(self):
        with pytest.raises(Refused):
            AccountingPeriod("bad", datetime.date(2026, 2, 1), JAN)

    def test_status_defaults_to_open(self):
        assert _calendar().by_name("2026-01").status is PeriodStatus.OPEN
