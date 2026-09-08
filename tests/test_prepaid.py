from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.prepaid import monthly_amortization

START = datetime.date(2026, 1, 1)


class TestSchedule:
    def test_a_year_of_insurance_expenses_monthly(self):
        sched = monthly_amortization(Money.of(1200, "USD"), START, 12)
        assert all(row.expensed == 10000 for row in sched.rows)
        assert sched.fully_amortized()

    def test_the_asset_reaches_exactly_zero(self):
        sched = monthly_amortization(Money.of(100, "USD"), START, 7)
        assert sched.rows[-1].remaining == 0

    def test_a_single_month_prepayment_is_allowed(self):
        sched = monthly_amortization(Money.of(50, "USD"), START, 1)
        assert len(sched.rows) == 1
        assert sched.rows[0].expensed == 5000


class TestQueries:
    def test_expensed_through_a_date(self):
        sched = monthly_amortization(Money.of(1200, "USD"), START, 12)
        assert sched.expensed_through(datetime.date(2026, 4, 1)) == Money.of(400, "USD")

    def test_the_unamortized_asset_is_the_complement(self):
        sched = monthly_amortization(Money.of(1200, "USD"), START, 12)
        assert sched.unamortized_at(datetime.date(2026, 4, 1)) == Money.of(800, "USD")


class TestRefusals:
    def test_zero_months_is_refused(self):
        with pytest.raises(Refused):
            monthly_amortization(Money.of(100, "USD"), START, 0)

    def test_nothing_prepaid_is_refused(self):
        with pytest.raises(Refused):
            monthly_amortization(Money.zero("USD"), START, 3)
