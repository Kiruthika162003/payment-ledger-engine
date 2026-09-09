from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.layaway import LayawayPlan, LayawayState
from mint.money import Money

START = datetime.date(2026, 1, 1)
MID = datetime.date(2026, 2, 1)
DEADLINE = datetime.date(2026, 4, 1)
LATE = datetime.date(2026, 5, 1)


def _plan(**kwargs) -> LayawayPlan:
    base = {
        "id": "L-1",
        "price": Money.of(600, "USD"),
        "started": START,
        "deadline": DEADLINE,
    }
    base.update(kwargs)
    return LayawayPlan(**base)


class TestNotYetASale:
    def test_payments_are_a_liability_not_revenue(self):
        plan = _plan()
        plan.pay(Money.of(200, "USD"), MID)
        assert plan.deposit_liability() == Money.of(200, "USD")
        assert plan.revenue_recognized().is_zero()

    def test_the_goods_stay_in_inventory(self):
        plan = _plan()
        plan.pay(Money.of(200, "USD"), MID)
        assert plan.goods_still_in_inventory()

    def test_progress_is_reported(self):
        plan = _plan()
        plan.pay(Money.of(200, "USD"), MID)
        assert plan.progress() == Fraction(1, 3)
        assert plan.outstanding() == Money.of(400, "USD")


class TestCompletion:
    def test_the_final_payment_makes_the_sale(self):
        plan = _plan()
        plan.pay(Money.of(300, "USD"), MID)
        plan.pay(Money.of(300, "USD"), MID)
        assert plan.is_complete()
        assert plan.state is LayawayState.COMPLETED
        assert plan.revenue_recognized() == Money.of(600, "USD")

    def test_the_liability_becomes_revenue(self):
        plan = _plan()
        plan.pay(Money.of(600, "USD"), MID)
        assert plan.deposit_liability().is_zero()
        assert not plan.goods_still_in_inventory()

    def test_overpaying_is_refused(self):
        plan = _plan()
        with pytest.raises(Refused):
            plan.pay(Money.of(700, "USD"), MID)

    def test_paying_a_completed_plan_is_refused(self):
        plan = _plan()
        plan.pay(Money.of(600, "USD"), MID)
        with pytest.raises(Refused):
            plan.pay(Money.of(1, "USD"), MID)


class TestCancellation:
    def test_a_cancellation_refunds_less_the_fee(self):
        plan = _plan()
        plan.pay(Money.of(300, "USD"), MID)
        refund = plan.cancel(MID)
        assert plan.cancellation_fee() == Money.of(60, "USD")
        assert refund == Money.of(240, "USD")
        assert plan.state is LayawayState.CANCELLED

    def test_the_fee_is_capped(self):
        plan = _plan(cancellation_cap=Money.of(25, "USD"))
        plan.pay(Money.of(300, "USD"), MID)
        assert plan.cancellation_fee() == Money.of(25, "USD")

    def test_the_fee_never_exceeds_what_was_paid(self):
        plan = _plan()
        plan.pay(Money.of(10, "USD"), MID)
        assert plan.cancellation_fee() == Money.of(10, "USD")

    def test_cancelling_twice_is_refused(self):
        plan = _plan()
        plan.pay(Money.of(100, "USD"), MID)
        plan.cancel(MID)
        with pytest.raises(Refused):
            plan.cancel(MID)


class TestDeadline:
    def test_paying_after_the_deadline_is_refused(self):
        plan = _plan()
        with pytest.raises(Refused) as caught:
            plan.pay(Money.of(100, "USD"), LATE)
        assert "reinstated" in str(caught.value)

    def test_forfeiting_before_the_deadline_is_refused(self):
        plan = _plan()
        plan.pay(Money.of(100, "USD"), MID)
        with pytest.raises(Refused):
            plan.forfeit(MID)

    def test_forfeiting_after_it_takes_the_deposit(self):
        plan = _plan()
        plan.pay(Money.of(100, "USD"), MID)
        assert plan.forfeit(LATE) == Money.of(100, "USD")
        assert plan.state is LayawayState.FORFEITED


class TestConstruction:
    def test_a_deadline_before_the_start_is_refused(self):
        with pytest.raises(Refused):
            _plan(deadline=START)

    def test_a_full_cancellation_fee_is_refused(self):
        with pytest.raises(Refused):
            _plan(cancellation_rate=Fraction(1))

    def test_a_nonpositive_price_is_refused(self):
        with pytest.raises(Refused):
            _plan(price=Money.zero("USD"))
