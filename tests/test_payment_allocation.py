from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.payment_allocation import OpenInvoice, allocate_payment


def _inv(id_, amount, age):
    return OpenInvoice(id_, Money.of(amount, "USD"), age)


class TestOldestFirst:
    def test_the_oldest_invoice_is_settled_first(self):
        invoices = [_inv("new", 100, 5), _inv("old", 100, 40)]
        result = allocate_payment(Money.of(100, "USD"), invoices)
        assert result.applications[0].invoice_id == "old"
        assert result.applications[0].applied == 10000

    def test_a_partial_payment_splits_at_the_boundary(self):
        invoices = [_inv("a", 60, 30), _inv("b", 60, 20)]
        result = allocate_payment(Money.of(80, "USD"), invoices)
        assert [(a.invoice_id, a.applied) for a in result.applications] == [
            ("a", 6000),
            ("b", 2000),
        ]
        assert result.credit.is_zero()


class TestOverpayment:
    def test_the_excess_becomes_a_credit(self):
        invoices = [_inv("a", 50, 10)]
        result = allocate_payment(Money.of(80, "USD"), invoices)
        assert result.total_applied() == 5000
        assert result.credit == Money.of(30, "USD")

    def test_the_allocation_sums_back_to_the_payment(self):
        invoices = [_inv("a", 50, 10), _inv("b", 40, 5)]
        result = allocate_payment(Money.of(120, "USD"), invoices)
        assert result.total_applied() + result.credit.units == 12000


class TestRefusals:
    def test_a_nonpositive_payment_is_refused(self):
        with pytest.raises(Refused):
            allocate_payment(Money.zero("USD"), [_inv("a", 10, 1)])

    def test_a_nonpositive_invoice_balance_is_refused(self):
        with pytest.raises(Refused):
            allocate_payment(
                Money.of(10, "USD"), [OpenInvoice("a", Money.zero("USD"), 1)]
            )
