"""Payment terms: when a bill is due, and what a fast payer gets off.

Payment terms are written in a shorthand that hides real
arithmetic. Net thirty means the whole amount is due thirty days
from the invoice date. Two ten net thirty means the same, except a
payer who settles within ten days may take two percent off, which
is an enormous implied interest rate for twenty days of money and
the reason finance teams chase early-payment discounts. End of
month terms are different again: the clock starts at the end of the
invoice's month rather than its date, so invoices issued across a
month all fall due together, which is what makes a supplier's
collections predictable. This module computes the due date, the
discount deadline, and the amount actually owed on a given payment
date, applying the discount only when the payment genuinely lands
inside the window, since a discount taken late is a short payment
the supplier will chase. It refuses terms whose discount window
outlasts the due date, because a discount available after the money
is already late is not a term anyone meant to write.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from mint.calendarutil import end_of_month
from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


class TermsKind(Enum):
    NET = "net"
    END_OF_MONTH = "end_of_month"


@dataclass(frozen=True)
class PaymentTerms:
    net_days: int
    discount_percent: Fraction = Fraction(0)
    discount_days: int = 0
    kind: TermsKind = TermsKind.NET

    def __post_init__(self) -> None:
        if self.net_days < 0 or self.discount_days < 0:
            raise Refused("payment terms count days forward, never backward")
        if self.discount_percent < 0 or self.discount_percent >= 1:
            raise Refused("an early-payment discount is a fraction below one")
        if self.discount_days > self.net_days:
            raise Refused(
                "the discount window outlasts the due date; a discount "
                "available after the money is late is not a term anyone meant"
            )

    def _base(self, invoice_date: datetime.date) -> datetime.date:
        if self.kind is TermsKind.END_OF_MONTH:
            return end_of_month(invoice_date)
        return invoice_date

    def due_date(self, invoice_date: datetime.date) -> datetime.date:
        return self._base(invoice_date) + datetime.timedelta(days=self.net_days)

    def discount_deadline(self, invoice_date: datetime.date) -> datetime.date:
        return self._base(invoice_date) + datetime.timedelta(days=self.discount_days)

    def offers_discount(self) -> bool:
        return self.discount_percent > 0 and self.discount_days > 0

    def discount_available_on(
        self, invoice_date: datetime.date, pay_date: datetime.date
    ) -> bool:
        return self.offers_discount() and pay_date <= self.discount_deadline(invoice_date)

    def amount_due(
        self, total: Money, invoice_date: datetime.date, pay_date: datetime.date
    ) -> Money:
        if not self.discount_available_on(invoice_date, pay_date):
            return total
        return total - scale(total, self.discount_percent, Rounding.HALF_EVEN)

    def days_overdue(self, invoice_date: datetime.date, as_of: datetime.date) -> int:
        return max(0, (as_of - self.due_date(invoice_date)).days)

    def is_overdue(self, invoice_date: datetime.date, as_of: datetime.date) -> bool:
        return as_of > self.due_date(invoice_date)

    def label(self) -> str:
        if self.kind is TermsKind.END_OF_MONTH:
            return f"net {self.net_days} EOM"
        if self.offers_discount():
            percent = float(self.discount_percent * 100)
            return f"{percent:g}/{self.discount_days} net {self.net_days}"
        return f"net {self.net_days}"
