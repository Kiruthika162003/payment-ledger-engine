"""Government grants: recognized as the cost they subsidize is incurred, not when received.

A grant is not income the day the money arrives. It is recognized
as the business incurs the costs the grant was meant to cover, so a
grant toward an asset is released to income across the asset's
life, matching the depreciation it offsets, and a grant toward
wages is recognized as those wages are paid. Recognizing it on
receipt would show a year of enormous profit followed by years of
depreciation with nothing against it, which is exactly the
mismatch the rule exists to prevent. This module holds both kinds
and releases them on the right schedule. The clawback is the part
that bites: most grants carry conditions, and breaching them makes
the unreleased balance repayable and often some of what was already
recognized too. The module tracks the repayable amount and refuses
to release further once a breach is recorded, since continuing to
take grant income while knowing it must be repaid is recognizing
revenue that has already been lost.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.errors import Refused
from mint.money import Money
from mint.rounding import split


class GrantKind(Enum):
    ASSET_RELATED = "asset_related"
    INCOME_RELATED = "income_related"


@dataclass
class Grant:
    id: str
    amount: Money
    kind: GrantKind
    received: datetime.date
    periods: int
    released: Money | None = None
    breached_on: datetime.date | None = None
    schedule: tuple[int, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.amount.is_positive():
            raise Refused("a grant is for a positive amount")
        if self.periods < 1:
            raise Refused(
                "a grant is released over at least one period; recognizing it "
                "all on receipt is the mismatch the rule exists to prevent"
            )
        if self.released is None:
            self.released = Money.zero(self.amount.currency)
        if not self.schedule:
            self.schedule = tuple(
                share.units for share in split(self.amount, self.periods)
            )

    def deferred_balance(self) -> Money:
        return self.amount - self.released

    def is_breached(self) -> bool:
        return self.breached_on is not None

    def periods_released(self) -> int:
        consumed = 0
        running = 0
        for units in self.schedule:
            if running >= self.released.units:
                break
            running += units
            consumed += 1
        return consumed

    def release_next(self) -> Money:
        if self.is_breached():
            raise Refused(
                f"grant {self.id!r} is in breach; releasing more would recognize "
                "revenue that has already been lost"
            )
        index = self.periods_released()
        if index >= len(self.schedule):
            raise Refused(f"grant {self.id!r} is fully released")
        amount = Money.from_minor(self.schedule[index], self.amount.currency)
        self.released = self.released + amount
        return amount

    def release_all_remaining(self) -> Money:
        if self.is_breached():
            raise Refused(f"grant {self.id!r} is in breach")
        remaining = self.deferred_balance()
        if remaining.is_zero():
            raise Refused(f"grant {self.id!r} is fully released")
        self.released = self.amount
        return remaining

    def breach(self, on: datetime.date, claw_back_recognized: bool = False) -> Money:
        if self.is_breached():
            raise Refused(f"grant {self.id!r} is already in breach")
        self.breached_on = on
        repayable = self.deferred_balance()
        if claw_back_recognized:
            repayable = self.amount
        return repayable

    def repayable(self) -> Money:
        if not self.is_breached():
            return Money.zero(self.amount.currency)
        return self.deferred_balance()

    def is_fully_released(self) -> bool:
        return self.deferred_balance().is_zero()


@dataclass
class GrantRegister:
    currency: str
    grants: list[Grant] = field(default_factory=list)

    def add(self, grant: Grant) -> Grant:
        if grant.amount.currency != self.currency:
            raise Refused(
                f"grant {grant.id!r} is in {grant.amount.currency}, not "
                f"{self.currency}"
            )
        if any(existing.id == grant.id for existing in self.grants):
            raise Refused(f"grant {grant.id!r} is already registered")
        self.grants.append(grant)
        return grant

    def total_deferred(self) -> Money:
        total = Money.zero(self.currency)
        for grant in self.grants:
            total = total + grant.deferred_balance()
        return total

    def total_released(self) -> Money:
        total = Money.zero(self.currency)
        for grant in self.grants:
            total = total + grant.released
        return total

    def total_repayable(self) -> Money:
        total = Money.zero(self.currency)
        for grant in self.grants:
            total = total + grant.repayable()
        return total

    def of_kind(self, kind: GrantKind) -> list[Grant]:
        return [grant for grant in self.grants if grant.kind is kind]
