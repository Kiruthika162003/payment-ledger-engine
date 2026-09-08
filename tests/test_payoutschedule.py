from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.payoutschedule import Cadence, PayoutSchedule

# 2026-01-02 is a Friday.
FRIDAY = datetime.date(2026, 1, 2)
MONDAY = datetime.date(2026, 1, 5)
TUESDAY = datetime.date(2026, 1, 6)


def _schedule(**kwargs) -> PayoutSchedule:
    base = {"cadence": Cadence.DAILY, "delay_days": 2}
    base.update(kwargs)
    return PayoutSchedule(**base)


class TestBankingDays:
    def test_a_weekend_date_rolls_to_monday(self):
        saturday = datetime.date(2026, 1, 3)
        assert _schedule().next_banking_day(saturday) == MONDAY

    def test_a_weekday_is_unchanged(self):
        assert _schedule().next_banking_day(FRIDAY) == FRIDAY

    def test_a_holiday_rolls_too(self):
        schedule = _schedule(holidays=frozenset({MONDAY}))
        saturday = datetime.date(2026, 1, 3)
        assert schedule.next_banking_day(saturday) == TUESDAY


class TestDelay:
    def test_the_delay_is_counted_in_banking_days(self):
        # Friday plus two banking days is Tuesday, not Sunday.
        assert _schedule().funds_available_on(FRIDAY) == TUESDAY

    def test_a_zero_delay_lands_the_same_day(self):
        assert _schedule(delay_days=0).funds_available_on(FRIDAY) == FRIDAY

    def test_a_friday_sale_pays_out_on_a_banking_day(self):
        payout = _schedule().payout_for_sale(FRIDAY)
        assert payout.weekday() < 5

    def test_days_to_money_spans_the_weekend(self):
        assert _schedule().days_to_money(FRIDAY) == 4


class TestWeekly:
    def test_a_weekly_schedule_lands_on_its_weekday(self):
        schedule = _schedule(cadence=Cadence.WEEKLY, weekday=4)
        payout = schedule.next_payout_after(MONDAY)
        assert payout.weekday() == 4

    def test_it_never_returns_the_same_day(self):
        schedule = _schedule(cadence=Cadence.WEEKLY, weekday=FRIDAY.weekday())
        assert schedule.next_payout_after(FRIDAY) > FRIDAY

    def test_upcoming_payouts_march_forward(self):
        schedule = _schedule(cadence=Cadence.WEEKLY, weekday=4)
        dates = schedule.upcoming(MONDAY, 3)
        assert dates == sorted(dates)
        assert len(set(dates)) == 3


class TestMonthly:
    def test_a_monthly_schedule_lands_on_its_day(self):
        schedule = _schedule(cadence=Cadence.MONTHLY, day_of_month=15)
        payout = schedule.next_payout_after(datetime.date(2026, 3, 1))
        assert payout.day in (15, 16)

    def test_the_thirty_first_clamps_in_february(self):
        # The clamp lands it on 28 February, which in 2026 is a Saturday, so
        # the banking-day roll then carries it to Monday 2 March. The point
        # is that it does not vanish, not that it stays inside February.
        schedule = _schedule(cadence=Cadence.MONTHLY, day_of_month=31)
        payout = schedule.next_payout_after(datetime.date(2026, 2, 1))
        assert payout == datetime.date(2026, 3, 2)
        assert payout.weekday() < 5

    def test_a_monthly_payout_is_a_banking_day(self):
        schedule = _schedule(cadence=Cadence.MONTHLY, day_of_month=4)
        payout = schedule.next_payout_after(datetime.date(2026, 1, 1))
        assert payout.weekday() < 5


class TestRefusals:
    def test_a_negative_delay_is_refused(self):
        with pytest.raises(Refused):
            _schedule(delay_days=-1)

    def test_an_impossible_weekday_is_refused(self):
        with pytest.raises(Refused):
            _schedule(weekday=9)

    def test_an_impossible_day_of_month_is_refused(self):
        with pytest.raises(Refused):
            _schedule(day_of_month=0)

    def test_a_zero_preview_is_refused(self):
        with pytest.raises(Refused):
            _schedule().upcoming(FRIDAY, 0)
