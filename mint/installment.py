"""Installment plans: splitting a total across dated payments without losing a cent.

An installment plan takes one amount and spreads it across several
dated payments, and the only thing it must never do is lose or
invent money in the spreading. This module builds the plan on top
of the allocation that already conserves the cent, so a hundred
dollars in three installments is thirty-four then thirty-three then
thirty-three and the payments add back to the hundred exactly. The
remainder cent lands on the first payment rather than the last by
default, because a customer would rather pay the odd cent up front
than discover a slightly larger final payment, and the choice is
explicit so a lender with the opposite policy can say so. Due dates
march from a first date by a fixed interval, and the plan reports
each payment with its date so a scheduler can post reminders and a
ledger can recognize each payment as it falls due. A plan of zero
payments is refused, since a total that goes nowhere is not a plan,
and a non-positive total is refused, since there is nothing to
spread.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from mint.errors import Refused
from mint.money import Money
from mint.rounding import split


@dataclass(frozen=True)
class Installment:
    number: int
    due: datetime.date
    amount: Money


@dataclass(frozen=True)
class InstallmentPlan:
    total: Money
    installments: tuple[Installment, ...]

    def count(self) -> int:
        return len(self.installments)

    def sums_back(self) -> bool:
        total = Money.zero(self.total.currency)
        for installment in self.installments:
            total = total + installment.amount
        return total == self.total

    def final_due(self) -> datetime.date:
        return self.installments[-1].due


def plan(
    total: Money,
    count: int,
    first_due: datetime.date,
    interval_days: int,
    remainder_first: bool = True,
) -> InstallmentPlan:
    if count < 1:
        raise Refused("an installment plan needs at least one payment")
    if not total.is_positive():
        raise Refused("there is nothing to spread across installments")
    if interval_days < 1:
        raise Refused("installments need a positive interval between them")
    shares = split(total, count)
    if not remainder_first:
        shares = list(reversed(shares))
    installments = tuple(
        Installment(
            number=index + 1,
            due=first_due + datetime.timedelta(days=interval_days * index),
            amount=amount,
        )
        for index, amount in enumerate(shares)
    )
    return InstallmentPlan(total=total, installments=installments)
