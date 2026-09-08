"""Prepaid expenses: paying up front, expensing across the months it covers.

A year of insurance paid in January is not a January expense; it is
an asset that becomes expense at a twelfth a month, and treating it
otherwise makes January look terrible and the following eleven
months look better than they were. Prepaid amortization is the
mirror of deferred revenue, and this module builds the same shape
of schedule from the other side: the payment is capitalized as an
asset and released to expense across the coverage period with the
cent conserved, so the asset reaches exactly zero at the end
instead of leaving a stub that sits on the balance sheet forever
because each month rounded independently. The schedule reports the
expense recognized, the cumulative, and the remaining unamortized
asset for each period. The coverage period is stated in months from
a start date, and a payment covering a single month is allowed
without ceremony, since a one-month prepayment is a real thing and
refusing it would push callers to special-case the trivial path.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from mint.calendarutil import add_months
from mint.errors import Refused
from mint.money import Money
from mint.rounding import split


@dataclass(frozen=True)
class AmortizationRow:
    period: int
    date: datetime.date
    expensed: int
    cumulative: int
    remaining: int


@dataclass(frozen=True)
class PrepaidSchedule:
    paid: Money
    rows: tuple[AmortizationRow, ...]

    def expensed_through(self, as_of: datetime.date) -> Money:
        total = 0
        for row in self.rows:
            if row.date <= as_of:
                total = row.cumulative
        return Money.from_minor(total, self.paid.currency)

    def unamortized_at(self, as_of: datetime.date) -> Money:
        return self.paid - self.expensed_through(as_of)

    def fully_amortized(self) -> bool:
        return bool(self.rows) and self.rows[-1].remaining == 0


def monthly_amortization(
    paid: Money, start: datetime.date, months: int
) -> PrepaidSchedule:
    if months < 1:
        raise Refused("a prepayment covers at least one month")
    if not paid.is_positive():
        raise Refused("there is nothing prepaid to amortize")
    shares = split(paid, months)
    rows = []
    cumulative = 0
    for index, share in enumerate(shares):
        cumulative += share.units
        rows.append(
            AmortizationRow(
                period=index + 1,
                date=add_months(start, index),
                expensed=share.units,
                cumulative=cumulative,
                remaining=paid.units - cumulative,
            )
        )
    return PrepaidSchedule(paid=paid, rows=tuple(rows))
