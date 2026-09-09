"""Guarantees and letters of credit: an obligation that costs nothing until it does.

A bank guarantee is a promise to pay if somebody else does not, and
its whole accounting difficulty is that it usually costs nothing.
It sits off the balance sheet as a contingent liability, accruing
only a commission for the privilege, until the day it is called, at
which point the full face value becomes a real liability at once.
Treating the maximum exposure as though it were a liability from
the start overstates the balance sheet; treating it as nothing at
all understates the risk, which is why it is disclosed rather than
either. This module tracks the live exposure, accrues the
commission over the guarantee's life rather than charging it at
issue, and handles the call: a drawing converts that much of the
contingent amount into a real debt and reduces what remains
available. A guarantee expires unused far more often than it is
called, and the module reports expiry as the ordinary outcome it is
rather than requiring a cancellation.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction

from mint.daycount import DayCount, year_fraction
from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


class GuaranteeState(Enum):
    LIVE = "live"
    PARTLY_CALLED = "partly_called"
    CALLED = "called"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Drawing:
    date: datetime.date
    amount: Money
    reason: str


@dataclass
class Guarantee:
    id: str
    beneficiary: str
    face_value: Money
    issued: datetime.date
    expires: datetime.date
    commission_rate: Fraction = Fraction(0)
    convention: DayCount = DayCount.ACT_360
    drawings: list[Drawing] = field(default_factory=list)
    cancelled_on: datetime.date | None = None

    def __post_init__(self) -> None:
        if not self.face_value.is_positive():
            raise Refused("a guarantee has a positive face value")
        if self.expires <= self.issued:
            raise Refused("a guarantee expires after it is issued")
        if self.commission_rate < 0:
            raise Refused("a commission rate is not negative")

    def drawn_total(self) -> Money:
        total = Money.zero(self.face_value.currency)
        for drawing in self.drawings:
            total = total + drawing.amount
        return total

    def available(self) -> Money:
        return self.face_value - self.drawn_total()

    def state(self, as_of: datetime.date) -> GuaranteeState:
        if self.cancelled_on is not None and as_of >= self.cancelled_on:
            return GuaranteeState.CANCELLED
        if self.available().is_zero():
            return GuaranteeState.CALLED
        if as_of > self.expires:
            # The ordinary outcome, not an exception needing a cancellation.
            return GuaranteeState.EXPIRED
        if self.drawn_total().is_positive():
            return GuaranteeState.PARTLY_CALLED
        return GuaranteeState.LIVE

    def contingent_exposure(self, as_of: datetime.date) -> Money:
        # Disclosed, never carried as a liability until it is called.
        if self.state(as_of) in (GuaranteeState.EXPIRED, GuaranteeState.CANCELLED):
            return Money.zero(self.face_value.currency)
        return self.available()

    def real_liability(self) -> Money:
        return self.drawn_total()

    def commission_to(self, as_of: datetime.date) -> Money:
        if self.commission_rate == 0:
            return Money.zero(self.face_value.currency)
        end = min(as_of, self.expires)
        if end <= self.issued:
            return Money.zero(self.face_value.currency)
        fraction = year_fraction(self.issued, end, self.convention)
        return round_money(
            self.face_value.times(self.commission_rate * fraction),
            self.face_value.currency,
            Rounding.HALF_EVEN,
        )

    def call(self, amount: Money, on: datetime.date, reason: str) -> Money:
        amount.same_currency(self.face_value)
        state = self.state(on)
        if state is GuaranteeState.EXPIRED:
            raise Refused(
                f"guarantee {self.id!r} expired on {self.expires.isoformat()} "
                "and can no longer be called"
            )
        if state is GuaranteeState.CANCELLED:
            raise Refused(f"guarantee {self.id!r} was cancelled")
        if not amount.is_positive():
            raise Refused("a call is for a positive amount")
        if not reason.strip():
            raise Refused("a call on a guarantee records why it was made")
        if amount > self.available():
            raise Refused(
                f"a call of {amount.format()} exceeds the "
                f"{self.available().format()} still available under guarantee "
                f"{self.id!r}"
            )
        self.drawings.append(Drawing(on, amount, reason.strip()))
        return self.available()

    def cancel(self, on: datetime.date) -> GuaranteeState:
        if self.cancelled_on is not None:
            raise Refused(f"guarantee {self.id!r} is already cancelled")
        if self.drawn_total().is_positive():
            raise Refused(
                f"guarantee {self.id!r} has been called and cannot be cancelled"
            )
        self.cancelled_on = on
        return GuaranteeState.CANCELLED


@dataclass
class GuaranteeBook:
    currency: str
    guarantees: list[Guarantee] = field(default_factory=list)

    def issue(self, guarantee: Guarantee) -> Guarantee:
        if guarantee.face_value.currency != self.currency:
            raise Refused(
                f"guarantee {guarantee.id!r} is in "
                f"{guarantee.face_value.currency}, not {self.currency}"
            )
        if any(existing.id == guarantee.id for existing in self.guarantees):
            raise Refused(f"guarantee {guarantee.id!r} is already on the book")
        self.guarantees.append(guarantee)
        return guarantee

    def total_contingent(self, as_of: datetime.date) -> Money:
        total = Money.zero(self.currency)
        for guarantee in self.guarantees:
            total = total + guarantee.contingent_exposure(as_of)
        return total

    def total_liability(self) -> Money:
        total = Money.zero(self.currency)
        for guarantee in self.guarantees:
            total = total + guarantee.real_liability()
        return total

    def live(self, as_of: datetime.date) -> list[Guarantee]:
        return [
            guarantee
            for guarantee in self.guarantees
            if guarantee.state(as_of)
            in (GuaranteeState.LIVE, GuaranteeState.PARTLY_CALLED)
        ]
