from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.creditline import CreditLine
from mint.errors import Refused
from mint.money import Money

JAN1 = datetime.date(2026, 1, 1)
JAN20 = datetime.date(2026, 1, 20)
JAN22 = datetime.date(2026, 1, 22)
FEB1 = datetime.date(2026, 2, 1)


def _line(**kwargs) -> CreditLine:
    base = {
        "id": "cl1",
        "limit": Money.of(100000, "USD"),
        "annual_rate": Fraction(365, 10000),
    }
    base.update(kwargs)
    return CreditLine(**base)


class TestDrawing:
    def test_drawing_reduces_headroom(self):
        line = _line()
        line.draw(Money.of(40000, "USD"), JAN1)
        assert line.drawn(JAN1) == Money.of(40000, "USD")
        assert line.available(JAN1) == Money.of(60000, "USD")

    def test_repaying_restores_headroom(self):
        line = _line()
        line.draw(Money.of(40000, "USD"), JAN1)
        line.repay(Money.of(15000, "USD"), JAN20)
        assert line.drawn(JAN20) == Money.of(25000, "USD")

    def test_drawing_past_the_limit_names_the_headroom(self):
        line = _line()
        line.draw(Money.of(90000, "USD"), JAN1)
        with pytest.raises(Refused) as caught:
            line.draw(Money.of(20000, "USD"), JAN1)
        assert "headroom" in str(caught.value)

    def test_repaying_more_than_drawn_is_refused(self):
        line = _line()
        line.draw(Money.of(10000, "USD"), JAN1)
        with pytest.raises(Refused):
            line.repay(Money.of(20000, "USD"), JAN1)


class TestInterest:
    def test_interest_accrues_only_while_drawn(self):
        line = _line()
        line.draw(Money.of(100000, "USD"), JAN20)
        line.repay(Money.of(100000, "USD"), JAN22)
        # Two days at 3.65% annual on 100000 is about 20.00.
        interest = line.interest_for(JAN1, FEB1)
        assert interest == Money.of(20, "USD")

    def test_an_undrawn_line_accrues_no_interest(self):
        line = _line()
        assert line.interest_for(JAN1, FEB1).is_zero()

    def test_a_month_end_balance_would_have_missed_it(self):
        line = _line()
        line.draw(Money.of(100000, "USD"), JAN20)
        line.repay(Money.of(100000, "USD"), JAN22)
        assert line.drawn(FEB1).is_zero()
        assert line.interest_for(JAN1, FEB1).is_positive()

    def test_a_backward_period_is_refused(self):
        with pytest.raises(Refused):
            _line().interest_for(FEB1, JAN1)


class TestCommitmentFee:
    def test_the_undrawn_portion_carries_a_fee(self):
        line = _line(commitment_rate=Fraction(365, 100000))
        line.draw(Money.of(50000, "USD"), JAN1)
        fee = line.commitment_fee_for(JAN1, FEB1)
        assert fee.is_positive()

    def test_no_fee_when_the_rate_is_zero(self):
        assert _line().commitment_fee_for(JAN1, FEB1).is_zero()


class TestLimitChanges:
    def test_reducing_the_limit_blocks_new_draws(self):
        line = _line()
        line.draw(Money.of(80000, "USD"), JAN1)
        line.reduce_limit(Money.of(60000, "USD"), JAN1)
        assert line.available(JAN1).is_zero()
        assert line.drawn(JAN1) == Money.of(80000, "USD")

    def test_raising_a_limit_through_reduce_is_refused(self):
        with pytest.raises(Refused):
            _line().reduce_limit(Money.of(200000, "USD"), JAN1)
