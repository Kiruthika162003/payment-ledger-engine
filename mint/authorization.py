"""Authorizations: money reserved but not yet moved, captured in pieces or let go.

A card authorization is a promise, not a payment: it reserves an
amount so the customer cannot spend it twice, but no money moves
until the merchant captures. This module models that promise as a
small state machine, because the states and their transitions are
exactly where payment systems leak. An authorization can be
captured all at once, or in pieces as goods ship, up to but never
beyond the amount authorized, and the refusal of an over-capture
names both the amount asked and the amount still available so an
operator sees the gap. It can be voided, which releases whatever
remains and forbids further capture, and a void of an
authorization with nothing left to release is refused rather than
silently doing nothing, since a no-op dressed as success hides a
bug. Authorizations expire, and a capture dated after the expiry
is refused, because the reserved funds are gone and capturing
against them would post money the customer never agreed was still
held. The status is derived from the captures and the void flag
and the date rather than stored, so it can never drift out of
agreement with the events that produced it.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.errors import InsufficientFunds, Refused
from mint.money import Money


class HoldStatus(Enum):
    OPEN = "open"
    PARTIALLY_CAPTURED = "partially_captured"
    CAPTURED = "captured"
    VOIDED = "voided"
    EXPIRED = "expired"


@dataclass(frozen=True)
class Capture:
    amount: Money
    date: datetime.date


@dataclass
class Authorization:
    id: str
    amount: Money
    created: datetime.date
    expires: datetime.date | None = None
    captures: list[Capture] = field(default_factory=list)
    voided_on: datetime.date | None = None

    def __post_init__(self) -> None:
        if not self.amount.is_positive():
            raise Refused("an authorization reserves a positive amount or none at all")
        if self.expires is not None and self.expires < self.created:
            raise Refused("an authorization cannot expire before it is created")

    def captured_total(self) -> Money:
        total = Money.zero(self.amount.currency)
        for capture in self.captures:
            total = total + capture.amount
        return total

    def remaining(self) -> Money:
        return self.amount - self.captured_total()

    def is_expired(self, as_of: datetime.date) -> bool:
        return self.expires is not None and as_of > self.expires

    def status(self, as_of: datetime.date | None = None) -> HoldStatus:
        moment = as_of or self.created
        if self.voided_on is not None:
            return HoldStatus.VOIDED
        if self.remaining().is_zero():
            return HoldStatus.CAPTURED
        if self.is_expired(moment):
            return HoldStatus.EXPIRED
        if self.captured_total().is_positive():
            return HoldStatus.PARTIALLY_CAPTURED
        return HoldStatus.OPEN

    def capture(self, amount: Money, on: datetime.date) -> Capture:
        amount.same_currency(self.amount)
        if self.voided_on is not None:
            raise Refused(
                f"authorization {self.id!r} was voided on "
                f"{self.voided_on.isoformat()} and cannot be captured"
            )
        if self.is_expired(on):
            raise Refused(
                f"authorization {self.id!r} expired on "
                f"{self.expires.isoformat()}; the reserved funds are gone"
            )
        if not amount.is_positive():
            raise Refused("a capture takes a positive amount")
        if amount > self.remaining():
            raise InsufficientFunds(
                f"a capture of {amount.format()} exceeds the "
                f"{self.remaining().format()} still held on authorization {self.id!r}"
            )
        capture = Capture(amount, on)
        self.captures.append(capture)
        return capture

    def void(self, on: datetime.date) -> Money:
        if self.voided_on is not None:
            raise Refused(f"authorization {self.id!r} is already voided")
        released = self.remaining()
        if released.is_zero():
            raise Refused(
                f"authorization {self.id!r} is fully captured; there is "
                "nothing left to void"
            )
        self.voided_on = on
        return released
