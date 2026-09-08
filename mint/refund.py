"""Refunds: giving captured money back, never more than was taken.

A refund is the reverse of a capture, and the one rule that keeps
it honest is that the refunds against a charge can never exceed
what the charge captured. A system that lets a refund run past the
capture is one merchant keystroke away from paying customers to
shop there, so this module tracks the refunded total against the
captured amount and refuses the refund that would overshoot,
naming how much is still refundable. Refunds accumulate, since a
charge is often returned in pieces as items come back, and the
charge reports whether it is now fully refunded so downstream
ledger postings and customer notices can react. A refund carries a
reason, because a return with no reason is the line an auditor
stops on, and a refund in a different currency than the charge is
refused outright rather than converted at some rate nobody chose,
since the money went out in one currency and comes back in the
same one. A full reversal is just a refund of everything still
refundable, offered as its own verb so the common case reads
clearly at the call site.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class Refund:
    amount: Money
    date: datetime.date
    reason: str


@dataclass
class Charge:
    id: str
    captured: Money
    date: datetime.date
    refunds: list[Refund] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.captured.is_positive():
            raise Refused("a charge captures a positive amount")

    def refunded_total(self) -> Money:
        total = Money.zero(self.captured.currency)
        for refund in self.refunds:
            total = total + refund.amount
        return total

    def refundable(self) -> Money:
        return self.captured - self.refunded_total()

    def is_fully_refunded(self) -> bool:
        return self.refundable().is_zero()

    def refund(self, amount: Money, on: datetime.date, reason: str) -> Refund:
        amount.same_currency(self.captured)
        if not amount.is_positive():
            raise Refused("a refund returns a positive amount")
        if not reason.strip():
            raise Refused(
                "a refund needs a reason; an unexplained return is the line "
                "an auditor stops on"
            )
        if amount > self.refundable():
            raise Refused(
                f"a refund of {amount.format()} exceeds the "
                f"{self.refundable().format()} still refundable on charge {self.id!r}"
            )
        refund = Refund(amount, on, reason.strip())
        self.refunds.append(refund)
        return refund

    def reverse(self, on: datetime.date, reason: str) -> Refund:
        remaining = self.refundable()
        if remaining.is_zero():
            raise Refused(
                f"charge {self.id!r} is already fully refunded; there is "
                "nothing left to reverse"
            )
        return self.refund(remaining, on, reason)
