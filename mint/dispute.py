"""Disputes: a chargeback's lifecycle, from opened to won, lost, or conceded.

When a cardholder disputes a charge, the bank pulls the funds back
and opens a window in which the merchant may contest it. The
outcome is not a boolean but a small lifecycle, and getting the
lifecycle wrong posts money in the wrong direction, so this module
makes the states explicit. A dispute opens for an amount that
cannot exceed the charge it contests, since a bank cannot claw
back more than was paid. From open, the merchant may submit
evidence, which moves it under review, or accept it, conceding
immediately. A dispute under review resolves as won, and the held
funds return to the merchant, or lost, and the reversal stands.
Every terminal state is final: submitting evidence on a resolved
dispute is refused, and resolving one twice is refused, because a
dispute that can be reopened by a stray call is a dispute whose
ledger effect no one can predict. The amount and the outcome
together are what the ledger integration needs to post the
reversal or release, and the module reports both plainly rather
than leaving the caller to infer them from the state.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.errors import Refused
from mint.money import Money


class DisputeStatus(Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    WON = "won"
    LOST = "lost"
    ACCEPTED = "accepted"


_TERMINAL = frozenset({DisputeStatus.WON, DisputeStatus.LOST, DisputeStatus.ACCEPTED})


@dataclass
class Dispute:
    id: str
    charge_id: str
    amount: Money
    opened: datetime.date
    charge_amount: Money
    status: DisputeStatus = DisputeStatus.OPEN
    evidence: list[str] = field(default_factory=list)
    reviewed_on: datetime.date | None = None
    resolved_on: datetime.date | None = None

    def __post_init__(self) -> None:
        self.amount.same_currency(self.charge_amount)
        if not self.amount.is_positive():
            raise Refused("a dispute contests a positive amount")
        if self.amount > self.charge_amount:
            raise Refused(
                f"a dispute of {self.amount.format()} exceeds the charge of "
                f"{self.charge_amount.format()}; a bank cannot claw back more "
                "than was paid"
            )

    def is_open(self) -> bool:
        return self.status not in _TERMINAL

    def _guard_open(self, verb: str) -> None:
        if not self.is_open():
            raise Refused(
                f"dispute {self.id!r} is {self.status.value} and cannot be "
                f"{verb}; a terminal state is final"
            )

    def submit_evidence(self, text: str, on: datetime.date) -> None:
        self._guard_open("given more evidence")
        if not text.strip():
            raise Refused("evidence cannot be empty")
        self.evidence.append(text.strip())
        self.reviewed_on = on
        self.status = DisputeStatus.UNDER_REVIEW

    def accept(self, on: datetime.date) -> Money:
        self._guard_open("accepted")
        self.status = DisputeStatus.ACCEPTED
        self.resolved_on = on
        return self.amount

    def resolve(self, won: bool, on: datetime.date) -> DisputeStatus:
        self._guard_open("resolved")
        self.status = DisputeStatus.WON if won else DisputeStatus.LOST
        self.resolved_on = on
        return self.status

    def merchant_keeps_funds(self) -> bool:
        return self.status is DisputeStatus.WON

    def funds_reversed(self) -> Money:
        if self.status in (DisputeStatus.LOST, DisputeStatus.ACCEPTED):
            return self.amount
        return Money.zero(self.amount.currency)
