from __future__ import annotations

import datetime

import pytest

from mint.bill import Bill, BillStatus
from mint.errors import Refused
from mint.money import Money
from mint.terms import PaymentTerms

ISSUED = datetime.date(2026, 1, 10)
LATE = datetime.date(2026, 3, 1)


def _bill(amount: str = "500.00") -> Bill:
    return Bill("b1", "Acme", Money.of(amount, "USD"), ISSUED, PaymentTerms(net_days=30))


class TestApproval:
    def test_paying_an_unapproved_bill_is_refused(self):
        bill = _bill()
        with pytest.raises(Refused) as caught:
            bill.pay(Money.of(100, "USD"), ISSUED, "wire-1")
        assert "fraudulent invoice" in str(caught.value)

    def test_approval_names_the_approver(self):
        bill = _bill()
        bill.approve("controller")
        assert bill.status is BillStatus.APPROVED
        assert bill.approved_by == "controller"

    def test_an_anonymous_approval_is_refused(self):
        with pytest.raises(Refused):
            _bill().approve("   ")


class TestPayment:
    def test_partial_payments_reduce_the_outstanding(self):
        bill = _bill()
        bill.approve("controller")
        bill.pay(Money.of(200, "USD"), ISSUED, "wire-1")
        assert bill.outstanding() == Money.of(300, "USD")
        assert not bill.is_paid()

    def test_full_payment_marks_it_paid(self):
        bill = _bill()
        bill.approve("controller")
        bill.pay(Money.of(500, "USD"), ISSUED, "wire-1")
        assert bill.is_paid()
        assert bill.status is BillStatus.PAID

    def test_overpaying_a_vendor_is_refused(self):
        bill = _bill()
        bill.approve("controller")
        with pytest.raises(Refused) as caught:
            bill.pay(Money.of(600, "USD"), ISSUED, "wire-1")
        assert "outstanding" in str(caught.value)


class TestDue:
    def test_the_due_date_comes_from_the_terms(self):
        assert _bill().due_date() == datetime.date(2026, 2, 9)

    def test_an_unpaid_bill_goes_overdue(self):
        bill = _bill()
        assert bill.is_overdue(LATE)

    def test_a_paid_bill_is_never_overdue(self):
        bill = _bill()
        bill.approve("controller")
        bill.pay(Money.of(500, "USD"), ISSUED, "wire-1")
        assert not bill.is_overdue(LATE)


class TestVoid:
    def test_an_untouched_bill_can_be_voided(self):
        bill = _bill()
        assert bill.void() is BillStatus.VOID

    def test_a_partly_paid_bill_cannot_be_voided(self):
        bill = _bill()
        bill.approve("controller")
        bill.pay(Money.of(100, "USD"), ISSUED, "wire-1")
        with pytest.raises(Refused) as caught:
            bill.void()
        assert "credit it instead" in str(caught.value)

    def test_a_void_bill_cannot_be_paid(self):
        bill = _bill()
        bill.void()
        with pytest.raises(Refused):
            bill.pay(Money.of(1, "USD"), ISSUED, "wire-1")
