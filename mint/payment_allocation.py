"""Applying a payment across open invoices, oldest first, remainder as credit.

When a customer pays less than their full balance, the money has
to be applied to specific invoices, and the choice matters because
it decides which invoices age into collections and which are
cleared. The common and defensible policy is oldest first: apply
the payment to the invoice that has been outstanding longest until
it is settled, then the next, because letting the oldest debt sit
while newer ones clear is how a receivable quietly rots. This
module applies a payment that way, settling each invoice in turn
and splitting the payment exactly at the invoice that runs out of
money, so the last invoice touched may be left partly paid with the
precise remainder recorded. A payment larger than the whole balance
leaves an overpayment, which the module returns as a credit rather
than forcing onto an invoice that cannot hold it, since an
overpayment is the customer's money to carry forward, not the
merchant's to lose track of. A non-positive payment is refused,
because applying nothing is not an application, and the allocation
always sums back to the payment: what landed on invoices plus the
credit equals what was paid.
"""

from __future__ import annotations

from dataclasses import dataclass

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class OpenInvoice:
    id: str
    balance: Money
    age_days: int


@dataclass(frozen=True)
class Application:
    invoice_id: str
    applied: int


@dataclass(frozen=True)
class Allocation:
    applications: tuple[Application, ...]
    credit: Money

    def total_applied(self) -> int:
        return sum(a.applied for a in self.applications)


def allocate_payment(payment: Money, invoices: list[OpenInvoice]) -> Allocation:
    if not payment.is_positive():
        raise Refused("a payment applies a positive amount or it is not a payment")
    for invoice in invoices:
        invoice.balance.same_currency(payment)
        if not invoice.balance.is_positive():
            raise Refused(
                f"invoice {invoice.id!r} has no positive balance to pay down"
            )
    ordered = sorted(invoices, key=lambda inv: (-inv.age_days, inv.id))
    remaining = payment.units
    applications: list[Application] = []
    for invoice in ordered:
        if remaining <= 0:
            break
        take = min(remaining, invoice.balance.units)
        applications.append(Application(invoice.id, take))
        remaining -= take
    return Allocation(
        applications=tuple(applications),
        credit=Money.from_minor(remaining, payment.currency),
    )
