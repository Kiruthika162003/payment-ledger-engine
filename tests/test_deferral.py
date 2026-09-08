from __future__ import annotations

import datetime

import pytest

from mint.deferral import monthly_schedule
from mint.errors import Refused
from mint.money import Money

START = datetime.date(2026, 1, 1)


class TestSchedule:
    def test_a_year_recognized_monthly(self):
        sched = monthly_schedule(Money.of(1200, "USD"), START, 12)
        assert len(sched.rows) == 12
        assert all(row.recognized == 10000 for row in sched.rows)

    def test_the_cent_is_conserved_on_an_awkward_total(self):
        sched = monthly_schedule(Money.of(100, "USD"), START, 3)
        assert [r.recognized for r in sched.rows] == [3334, 3333, 3333]
        assert sum(r.recognized for r in sched.rows) == 10000

    def test_the_liability_reaches_exactly_zero(self):
        sched = monthly_schedule(Money.of(100, "USD"), START, 7)
        assert sched.rows[-1].deferred == 0
        assert sched.fully_recognized()


class TestQueries:
    def test_recognized_through_a_date(self):
        sched = monthly_schedule(Money.of(1200, "USD"), START, 12)
        assert sched.recognized_through(datetime.date(2026, 3, 1)) == Money.of(300, "USD")

    def test_deferred_is_the_complement(self):
        sched = monthly_schedule(Money.of(1200, "USD"), START, 12)
        assert sched.deferred_at(datetime.date(2026, 3, 1)) == Money.of(900, "USD")

    def test_nothing_is_recognized_before_the_start(self):
        sched = monthly_schedule(Money.of(1200, "USD"), START, 12)
        assert sched.recognized_through(datetime.date(2025, 12, 1)).is_zero()


class TestRefusals:
    def test_zero_months_is_refused(self):
        with pytest.raises(Refused):
            monthly_schedule(Money.of(100, "USD"), START, 0)

    def test_nothing_to_defer_is_refused(self):
        with pytest.raises(Refused):
            monthly_schedule(Money.zero("USD"), START, 3)
