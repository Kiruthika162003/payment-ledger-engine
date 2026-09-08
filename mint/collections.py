"""Collections: promises to pay, whether they were kept, and plans that survive a miss.

Collecting an overdue debt is a sequence of promises, and the only
thing worth tracking is whether they were kept. A promise to pay
records an amount and a date; when the date passes the promise is
either kept, partly kept, or broken, and a collector's next move
depends entirely on which. This module makes that determination
from the payments actually received rather than from a status
someone remembered to update, so a promise cannot be marked kept by
optimism. Payment plans are the structured version: a schedule of
instalments where missing one does not automatically void the
arrangement, because a plan cancelled on the first miss pushes a
borrower who was mostly complying straight into default, and most
collections policies allow a stated number of misses before the
plan fails. The module counts the misses and reports when the
threshold is crossed, and a plan whose instalments no longer cover
the debt is refused at creation, since a plan that cannot clear the
balance is a way of not collecting rather than a way of collecting.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.errors import Refused
from mint.money import Money
from mint.rounding import split


class PromiseState(Enum):
    OPEN = "open"
    KEPT = "kept"
    PARTLY_KEPT = "partly_kept"
    BROKEN = "broken"


@dataclass
class Promise:
    id: str
    amount: Money
    due: datetime.date
    received: Money | None = None

    def __post_init__(self) -> None:
        if not self.amount.is_positive():
            raise Refused("a promise to pay is for a positive amount")
        if self.received is None:
            self.received = Money.zero(self.amount.currency)

    def record_payment(self, amount: Money) -> Money:
        amount.same_currency(self.amount)
        if not amount.is_positive():
            raise Refused("a payment against a promise is positive")
        self.received = self.received + amount
        return self.received

    def state(self, as_of: datetime.date) -> PromiseState:
        # Determined from what arrived, never from a status someone remembered
        # to update.
        if self.received >= self.amount:
            return PromiseState.KEPT
        if as_of <= self.due:
            return PromiseState.OPEN
        if self.received.is_positive():
            return PromiseState.PARTLY_KEPT
        return PromiseState.BROKEN

    def shortfall(self) -> Money:
        gap = self.amount - self.received
        return gap if gap.is_positive() else Money.zero(self.amount.currency)


@dataclass
class PaymentPlan:
    id: str
    debt: Money
    instalments: list[Promise] = field(default_factory=list)
    misses_allowed: int = 2

    def build(
        self, count: int, first_due: datetime.date, interval_days: int
    ) -> list[Promise]:
        if count < 1:
            raise Refused("a payment plan needs at least one instalment")
        if interval_days < 1:
            raise Refused("instalments need a positive interval between them")
        shares = split(self.debt, count)
        self.instalments = [
            Promise(
                id=f"{self.id}-{index + 1}",
                amount=amount,
                due=first_due + datetime.timedelta(days=interval_days * index),
            )
            for index, amount in enumerate(shares)
        ]
        if not self.covers_the_debt():
            raise Refused(
                f"plan {self.id!r} does not clear the balance; a plan that "
                "cannot clear the debt is a way of not collecting"
            )
        return self.instalments

    def covers_the_debt(self) -> bool:
        total = Money.zero(self.debt.currency)
        for instalment in self.instalments:
            total = total + instalment.amount
        return total == self.debt

    def get(self, instalment_id: str) -> Promise:
        for instalment in self.instalments:
            if instalment.id == instalment_id:
                return instalment
        raise Refused(f"plan {self.id!r} has no instalment {instalment_id!r}")

    def received_total(self) -> Money:
        total = Money.zero(self.debt.currency)
        for instalment in self.instalments:
            total = total + instalment.received
        return total

    def outstanding(self) -> Money:
        return self.debt - self.received_total()

    def misses(self, as_of: datetime.date) -> int:
        return sum(
            1
            for instalment in self.instalments
            if instalment.state(as_of) in (PromiseState.BROKEN, PromiseState.PARTLY_KEPT)
        )

    def has_failed(self, as_of: datetime.date) -> bool:
        # A plan cancelled on the first miss pushes a mostly-complying
        # borrower straight into default.
        return self.misses(as_of) > self.misses_allowed

    def is_settled(self) -> bool:
        return self.outstanding().is_zero()

    def next_due(self, as_of: datetime.date) -> Promise | None:
        pending = [
            instalment
            for instalment in self.instalments
            if instalment.state(as_of) is not PromiseState.KEPT
        ]
        if not pending:
            return None
        return min(pending, key=lambda instalment: instalment.due)
