from __future__ import annotations

import datetime

import pytest

from mint.accrual import Accrual, AccrualKind
from mint.errors import Refused
from mint.money import Money

DEC31 = datetime.date(2026, 12, 31)
JAN1 = datetime.date(2027, 1, 1)


def _accrual(amount: str = "500.00") -> Accrual:
    return Accrual(
        "ac_1", AccrualKind.EXPENSE, Money.of(amount, "USD"), DEC31, JAN1
    )


class TestReversal:
    def test_an_accrual_reverses_in_the_next_period(self):
        accrual = _accrual()
        assert accrual.reverse(JAN1) == Money.of(500, "USD")
        assert accrual.is_reversed()

    def test_a_double_reversal_is_refused(self):
        accrual = _accrual()
        accrual.reverse(JAN1)
        with pytest.raises(Refused) as caught:
            accrual.reverse(JAN1)
        assert "phantom income" in str(caught.value)

    def test_reversing_early_is_refused(self):
        accrual = _accrual()
        with pytest.raises(Refused):
            accrual.reverse(DEC31)

    def test_it_is_outstanding_until_reversed(self):
        accrual = _accrual()
        assert accrual.is_outstanding(DEC31)
        accrual.reverse(JAN1)
        assert not accrual.is_outstanding(JAN1)


class TestSettlement:
    def test_settling_reports_the_estimate_error(self):
        accrual = _accrual("500.00")
        accrual.reverse(JAN1)
        difference = accrual.settle("INV-9", Money.of(540, "USD"))
        assert difference == Money.of(40, "USD")
        assert accrual.settled_by == "INV-9"

    def test_settling_before_reversal_is_refused(self):
        accrual = _accrual()
        with pytest.raises(Refused) as caught:
            accrual.settle("INV-9", Money.of(500, "USD"))
        assert "charged twice" in str(caught.value)


class TestConstruction:
    def test_a_nonpositive_accrual_is_refused(self):
        with pytest.raises(Refused):
            Accrual("x", AccrualKind.EXPENSE, Money.zero("USD"), DEC31, JAN1)

    def test_reversing_on_or_before_the_accrual_date_is_refused(self):
        with pytest.raises(Refused):
            Accrual("x", AccrualKind.REVENUE, Money.of(1, "USD"), DEC31, DEC31)
