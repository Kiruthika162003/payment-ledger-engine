from __future__ import annotations

import datetime

import pytest

from mint.errors import CurrencyMismatch, Refused
from mint.money import Money
from mint.refund import Charge

DAY = datetime.date(2026, 2, 1)


def _charge(amount: str = "100.00") -> Charge:
    return Charge("ch_1", Money.of(amount, "USD"), DAY)


class TestRefund:
    def test_a_partial_refund_reduces_what_is_refundable(self):
        charge = _charge()
        charge.refund(Money.of(30, "USD"), DAY, "one item returned")
        assert charge.refundable() == Money.of(70, "USD")
        assert not charge.is_fully_refunded()

    def test_refunds_accumulate_to_full(self):
        charge = _charge()
        charge.refund(Money.of(60, "USD"), DAY, "most items")
        charge.refund(Money.of(40, "USD"), DAY, "the rest")
        assert charge.is_fully_refunded()

    def test_over_refund_names_the_remaining(self):
        charge = _charge()
        charge.refund(Money.of(80, "USD"), DAY, "return")
        with pytest.raises(Refused) as caught:
            charge.refund(Money.of(30, "USD"), DAY, "return")
        assert "still refundable" in str(caught.value)

    def test_a_refund_needs_a_reason(self):
        with pytest.raises(Refused) as caught:
            _charge().refund(Money.of(10, "USD"), DAY, "   ")
        assert "needs a reason" in str(caught.value)

    def test_a_refund_in_another_currency_is_refused(self):
        with pytest.raises(CurrencyMismatch):
            _charge().refund(Money.of(10, "EUR"), DAY, "return")


class TestReverse:
    def test_reverse_returns_everything_refundable(self):
        charge = _charge()
        charge.refund(Money.of(25, "USD"), DAY, "partial")
        reversal = charge.reverse(DAY, "customer cancelled")
        assert reversal.amount == Money.of(75, "USD")
        assert charge.is_fully_refunded()

    def test_reversing_a_settled_charge_is_refused(self):
        charge = _charge()
        charge.reverse(DAY, "cancelled")
        with pytest.raises(Refused) as caught:
            charge.reverse(DAY, "again")
        assert "nothing left to reverse" in str(caught.value)


class TestConstruction:
    def test_a_nonpositive_charge_is_refused(self):
        with pytest.raises(Refused):
            Charge("ch_x", Money.zero("USD"), DAY)
