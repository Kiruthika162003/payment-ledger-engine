"""Accruals: recognizing what was incurred before the invoice arrives, then reversing.

Accrual accounting says an expense belongs to the period in which
it was incurred, not the period in which the invoice happened to
land, so at a period end the books accrue the electricity used in
December even though the bill comes in January. The mechanism that
keeps this from double-counting is the reversal: the accrual is
posted at period end and reversed on the first day of the next
period, so when the real invoice arrives it can be booked normally
without anyone having to remember to net it against an estimate.
This module models that pair. An accrual carries its amount, the
period it belongs to, and the date its reversal falls, and it
produces both entries from one declaration so the reversing half
cannot be forgotten, which is the classic accrual bug: an accrual
posted and never reversed overstates expense in the first period
and again in the second when the invoice lands. The module also
tracks whether an accrual has been settled by a real invoice and
refuses to reverse one twice, since a double reversal turns an
estimate into phantom income.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum

from mint.errors import Refused
from mint.money import Money


class AccrualKind(Enum):
    EXPENSE = "expense"
    REVENUE = "revenue"


@dataclass
class Accrual:
    id: str
    kind: AccrualKind
    amount: Money
    accrued_on: datetime.date
    reverses_on: datetime.date
    reversed_on: datetime.date | None = None
    settled_by: str | None = None

    def __post_init__(self) -> None:
        if not self.amount.is_positive():
            raise Refused("an accrual estimates a positive amount")
        if self.reverses_on <= self.accrued_on:
            raise Refused(
                "an accrual reverses in the period after it is accrued, not "
                "on or before the day it was posted"
            )

    def is_reversed(self) -> bool:
        return self.reversed_on is not None

    def reverse(self, on: datetime.date) -> Money:
        if self.is_reversed():
            raise Refused(
                f"accrual {self.id!r} was already reversed on "
                f"{self.reversed_on.isoformat()}; a second reversal turns an "
                "estimate into phantom income"
            )
        if on < self.reverses_on:
            raise Refused(
                f"accrual {self.id!r} reverses on "
                f"{self.reverses_on.isoformat()}, not before"
            )
        self.reversed_on = on
        return self.amount

    def settle(self, invoice_ref: str, actual: Money) -> Money:
        actual.same_currency(self.amount)
        if not self.is_reversed():
            raise Refused(
                f"accrual {self.id!r} must be reversed before the real invoice "
                "is booked, or the period is charged twice"
            )
        self.settled_by = invoice_ref
        return actual - self.amount

    def is_outstanding(self, as_of: datetime.date) -> bool:
        return not self.is_reversed() and as_of >= self.accrued_on
