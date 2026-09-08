"""Vendor bills: the payables mirror of an invoice, tracked to paid.

A bill is what an invoice looks like from the other side of the
transaction: someone else's invoice, owed by us, and the ledger
tracks it through approval and payment rather than merely storing
its total. The states matter because money leaves on them. A bill
arrives as received, is approved by someone with authority, and is
then payable; paying an unapproved bill is the control failure that
lets a fraudulent invoice through, so this module refuses it by
name. Payments apply against the bill and accumulate, and a payment
that would take the paid total past the bill amount is refused,
because overpaying a vendor is money that has to be chased back
rather than a rounding curiosity. The bill reports what remains
outstanding, whether it is fully paid, and whether it is overdue
against its terms as of a date, which are the three questions an
accounts-payable run asks of every bill it considers. Voiding is
allowed only before any payment lands, since a bill that has been
partly paid cannot be made to have never existed and must be
credited instead.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.errors import Refused
from mint.money import Money
from mint.terms import PaymentTerms


class BillStatus(Enum):
    RECEIVED = "received"
    APPROVED = "approved"
    PAID = "paid"
    VOID = "void"


@dataclass(frozen=True)
class BillPayment:
    date: datetime.date
    amount: Money
    reference: str


@dataclass
class Bill:
    id: str
    vendor: str
    amount: Money
    issued: datetime.date
    terms: PaymentTerms
    status: BillStatus = BillStatus.RECEIVED
    approved_by: str | None = None
    payments: list[BillPayment] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.amount.is_positive():
            raise Refused("a bill is for a positive amount")

    def due_date(self) -> datetime.date:
        return self.terms.due_date(self.issued)

    def paid_total(self) -> Money:
        total = Money.zero(self.amount.currency)
        for payment in self.payments:
            total = total + payment.amount
        return total

    def outstanding(self) -> Money:
        return self.amount - self.paid_total()

    def is_paid(self) -> bool:
        return self.outstanding().is_zero()

    def is_overdue(self, as_of: datetime.date) -> bool:
        return not self.is_paid() and self.terms.is_overdue(self.issued, as_of)

    def approve(self, approver: str) -> BillStatus:
        if self.status is BillStatus.VOID:
            raise Refused(f"bill {self.id!r} is void and cannot be approved")
        if not approver.strip():
            raise Refused("an approval names the person who gave it")
        self.approved_by = approver.strip()
        self.status = BillStatus.APPROVED
        return self.status

    def pay(self, amount: Money, on: datetime.date, reference: str) -> Money:
        amount.same_currency(self.amount)
        if self.status is BillStatus.RECEIVED:
            raise Refused(
                f"bill {self.id!r} has not been approved; paying an unapproved "
                "bill is how a fraudulent invoice gets through"
            )
        if self.status is BillStatus.VOID:
            raise Refused(f"bill {self.id!r} is void and cannot be paid")
        if not amount.is_positive():
            raise Refused("a payment against a bill is positive")
        if amount > self.outstanding():
            raise Refused(
                f"a payment of {amount.format()} exceeds the "
                f"{self.outstanding().format()} outstanding on bill {self.id!r}"
            )
        self.payments.append(BillPayment(on, amount, reference))
        if self.is_paid():
            self.status = BillStatus.PAID
        return self.outstanding()

    def void(self) -> BillStatus:
        if self.payments:
            raise Refused(
                f"bill {self.id!r} has payments against it and cannot be voided; "
                "credit it instead"
            )
        self.status = BillStatus.VOID
        return self.status
