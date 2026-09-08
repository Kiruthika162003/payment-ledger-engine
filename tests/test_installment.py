from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.installment import plan
from mint.money import Money

FIRST = datetime.date(2026, 1, 1)


class TestPlan:
    def test_a_hundred_in_three_conserves_the_cent(self):
        # 100 dollars is 10000 cents; a three-way split is 33.34, 33.33,
        # 33.33, with the odd cent up front, not dollar-level 34/33/33.
        result = plan(Money.of(100, "USD"), 3, FIRST, 30)
        assert [i.amount.units for i in result.installments] == [3334, 3333, 3333]
        assert result.sums_back()

    def test_due_dates_march_by_the_interval(self):
        result = plan(Money.of(100, "USD"), 3, FIRST, 30)
        assert [i.due for i in result.installments] == [
            FIRST,
            datetime.date(2026, 1, 31),
            datetime.date(2026, 3, 2),
        ]

    def test_remainder_can_go_last_instead(self):
        result = plan(Money.of(100, "USD"), 3, FIRST, 30, remainder_first=False)
        assert [i.amount.units for i in result.installments] == [3333, 3333, 3334]
        assert result.sums_back()

    def test_the_count_and_final_due(self):
        result = plan(Money.of(100, "USD"), 3, FIRST, 30)
        assert result.count() == 3
        assert result.final_due() == datetime.date(2026, 3, 2)


class TestRefusals:
    def test_zero_payments_is_refused(self):
        with pytest.raises(Refused):
            plan(Money.of(100, "USD"), 0, FIRST, 30)

    def test_a_nonpositive_total_is_refused(self):
        with pytest.raises(Refused):
            plan(Money.zero("USD"), 3, FIRST, 30)

    def test_a_nonpositive_interval_is_refused(self):
        with pytest.raises(Refused):
            plan(Money.of(100, "USD"), 3, FIRST, 0)
