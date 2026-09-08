from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.refundpolicy import (
    Condition,
    Reason,
    ReturnPolicy,
    quote_refund,
    standard_policy,
    within_window,
)

BOUGHT = datetime.date(2026, 1, 1)
SOON = datetime.date(2026, 1, 10)
LATE = datetime.date(2026, 3, 1)


def _quote(**kwargs):
    base = {
        "policy": standard_policy(),
        "price": Money.of(100, "USD"),
        "shipping_paid": Money.of(10, "USD"),
        "purchased_on": BOUGHT,
        "returned_on": SOON,
        "condition": Condition.UNOPENED,
        "reason": Reason.CHANGED_MIND,
    }
    base.update(kwargs)
    return quote_refund(**base)


class TestWindow:
    def test_a_return_inside_the_window_is_quoted(self):
        assert _quote().total.is_positive()

    def test_a_late_change_of_mind_is_refused(self):
        with pytest.raises(Refused) as caught:
            _quote(returned_on=LATE)
        assert "not the same as a refund of nothing" in str(caught.value)

    def test_a_late_faulty_return_is_still_accepted(self):
        quote = _quote(returned_on=LATE, reason=Reason.FAULTY)
        assert quote.total.is_positive()

    def test_within_window_reports_plainly(self):
        assert within_window(standard_policy(), BOUGHT, SOON)
        assert not within_window(standard_policy(), BOUGHT, LATE)

    def test_a_return_before_purchase_is_refused(self):
        with pytest.raises(Refused):
            _quote(returned_on=datetime.date(2025, 1, 1))


class TestRestocking:
    def test_unopened_goods_carry_no_restocking_fee(self):
        quote = _quote(condition=Condition.UNOPENED)
        assert quote.restocking_fee.is_zero()

    def test_opened_goods_carry_the_fee_on_a_change_of_mind(self):
        quote = _quote(condition=Condition.OPENED)
        assert quote.restocking_fee == Money.of(15, "USD")

    def test_a_faulty_return_carries_no_fee(self):
        quote = _quote(condition=Condition.OPENED, reason=Reason.FAULTY)
        assert quote.restocking_fee.is_zero()

    def test_the_fee_appears_as_a_named_deduction(self):
        quote = _quote(condition=Condition.OPENED)
        assert dict(quote.deductions)["restocking fee"] == 1500


class TestShipping:
    def test_shipping_comes_back_when_the_fault_is_ours(self):
        quote = _quote(reason=Reason.FAULTY)
        assert quote.shipping_refunded == Money.of(10, "USD")

    def test_shipping_stays_on_a_change_of_mind(self):
        quote = _quote()
        assert quote.shipping_refunded.is_zero()
        assert "shipping not refunded" in dict(quote.deductions)

    def test_a_policy_can_refund_shipping_either_way(self):
        policy = ReturnPolicy(
            window_days=30, refund_shipping_on_change_of_mind=True
        )
        quote = _quote(policy=policy)
        assert quote.shipping_refunded == Money.of(10, "USD")


class TestCondition:
    def test_damaged_goods_are_refused_unless_faulty(self):
        with pytest.raises(Refused) as caught:
            _quote(condition=Condition.DAMAGED)
        assert "unless the fault was ours" in str(caught.value)

    def test_damaged_faulty_goods_are_accepted(self):
        quote = _quote(condition=Condition.DAMAGED, reason=Reason.FAULTY)
        assert quote.total.is_positive()

    def test_a_policy_can_refuse_opened_goods(self):
        policy = ReturnPolicy(window_days=30, accept_opened=False)
        with pytest.raises(Refused):
            _quote(policy=policy, condition=Condition.OPENED)


class TestArithmetic:
    def test_the_quote_reconciles(self):
        assert _quote(condition=Condition.OPENED).reconciles()

    def test_a_faulty_return_refunds_everything(self):
        quote = _quote(reason=Reason.FAULTY)
        assert quote.total == Money.of(110, "USD")

    def test_an_invalid_restocking_rate_is_refused(self):
        with pytest.raises(Refused):
            ReturnPolicy(window_days=30, restocking_rate=Fraction(1))

    def test_a_negative_window_is_refused(self):
        with pytest.raises(Refused):
            ReturnPolicy(window_days=-1)
