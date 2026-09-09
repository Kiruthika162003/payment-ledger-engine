"""The tax point: which date decides the period a sale's tax belongs to.

Tax is accounted for in the period of the tax point, and the tax
point is not simply the invoice date. The basic rule is the date
the goods were supplied, but issuing an invoice within a short
window after supply moves the tax point to the invoice date, and
taking payment before supply creates an earlier tax point for the
amount received. The consequence is that one sale can have two tax
points, a deposit taken in March and the balance supplied in April
falling in different returns, and a system that uses one date for
the whole sale reports the wrong amount in both periods. This
module applies the rules in the order they actually override each
other and returns the tax points with the amounts attached, so a
return can be built from them. A payment after supply does not move
anything, since the tax point was already fixed, which is the
asymmetry people find surprising.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.errors import Refused
from mint.money import Money


class Trigger(Enum):
    SUPPLY = "supply"
    INVOICE_WITHIN_WINDOW = "invoice_within_window"
    PAYMENT_IN_ADVANCE = "payment_in_advance"


@dataclass(frozen=True)
class TaxPoint:
    date: datetime.date
    amount: Money
    trigger: Trigger

    def period(self) -> tuple[int, int]:
        return (self.date.year, self.date.month)


@dataclass
class Supply:
    id: str
    total: Money
    supplied_on: datetime.date
    invoiced_on: datetime.date | None = None
    invoice_window_days: int = 14
    advance_payments: list[tuple[datetime.date, Money]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.total.is_positive():
            raise Refused("a supply is for a positive amount")
        if self.invoice_window_days < 0:
            raise Refused("an invoice window is not negative")

    def receive_payment(self, on: datetime.date, amount: Money) -> Money:
        amount.same_currency(self.total)
        if not amount.is_positive():
            raise Refused("a payment is for a positive amount")
        if self.paid_in_advance() + amount > self.total and on < self.supplied_on:
            raise Refused(
                f"advance payments on supply {self.id!r} would exceed its total"
            )
        self.advance_payments.append((on, amount))
        return self.paid_in_advance()

    def paid_in_advance(self) -> Money:
        total = Money.zero(self.total.currency)
        for date, amount in self.advance_payments:
            if date < self.supplied_on:
                total = total + amount
        return total

    def basic_tax_point(self) -> datetime.date:
        return self.supplied_on

    def actual_tax_point(self) -> datetime.date:
        # An invoice inside the window overrides the supply date; one outside
        # it does not.
        if self.invoiced_on is None:
            return self.supplied_on
        gap = (self.invoiced_on - self.supplied_on).days
        if 0 <= gap <= self.invoice_window_days:
            return self.invoiced_on
        return self.supplied_on

    def tax_points(self) -> list[TaxPoint]:
        points: list[TaxPoint] = []
        advanced = Money.zero(self.total.currency)
        for date, amount in sorted(self.advance_payments):
            if date >= self.supplied_on:
                # A payment after supply moves nothing; the point was fixed.
                continue
            points.append(TaxPoint(date, amount, Trigger.PAYMENT_IN_ADVANCE))
            advanced = advanced + amount
        remainder = self.total - advanced
        if remainder.is_positive():
            date = self.actual_tax_point()
            trigger = (
                Trigger.INVOICE_WITHIN_WINDOW
                if date != self.supplied_on
                else Trigger.SUPPLY
            )
            points.append(TaxPoint(date, remainder, trigger))
        return points

    def spans_two_periods(self) -> bool:
        periods = {point.period() for point in self.tax_points()}
        return len(periods) > 1

    def amount_in_period(self, year: int, month: int) -> Money:
        total = Money.zero(self.total.currency)
        for point in self.tax_points():
            if point.period() == (year, month):
                total = total + point.amount
        return total

    def points_reconcile(self) -> bool:
        total = Money.zero(self.total.currency)
        for point in self.tax_points():
            total = total + point.amount
        return total == self.total
