"""Bonus pools: accruing what will be paid, on the performance actually achieved so far.

A bonus payable in March for last year's performance is last year's
cost, so it accrues through the year rather than landing in March.
The estimate is the awkward part, because the pool depends on
performance that is not finished yet, and accruing the target
bonus when the year is running behind overstates the cost while
accruing nothing until the target is passed understates it all year
and then lands a large charge in December. This module accrues on
performance to date against target, scaled by how much of the year
has elapsed, and recomputes the cumulative accrual each period so a
collapse in the fourth quarter produces a credit rather than a
running total that has to be unwound by hand. The pool is capped,
since most schemes have a maximum, and the cap is applied to the
pool rather than to each participant so an over-performing team
does not silently breach it. Individual shares come out of the
capped pool with the cent conserved, so what is promised is what is
funded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, allocate, round_money, scale


@dataclass(frozen=True)
class Participant:
    name: str
    weight: Fraction

    def __post_init__(self) -> None:
        if self.weight <= 0:
            raise Refused(f"participant {self.name!r} needs a positive weight")


@dataclass
class BonusPool:
    currency: str
    target_pool: Money
    maximum_pool: Money
    participants: list[Participant] = field(default_factory=list)
    accrued: Money | None = None

    def __post_init__(self) -> None:
        self.maximum_pool.same_currency(self.target_pool)
        if not self.target_pool.is_positive():
            raise Refused("a bonus pool has a positive target")
        if self.maximum_pool < self.target_pool:
            raise Refused(
                "a maximum pool below the target means the target can never be "
                "reached"
            )
        if self.accrued is None:
            self.accrued = Money.zero(self.currency)

    def add(self, participant: Participant) -> Participant:
        if any(existing.name == participant.name for existing in self.participants):
            raise Refused(f"{participant.name!r} is already in the pool")
        self.participants.append(participant)
        return participant

    def earned_pool(self, achievement: Fraction) -> Money:
        if achievement < 0:
            raise Refused("achievement against target is not negative")
        earned = scale(self.target_pool, achievement, Rounding.HALF_EVEN)
        # The cap applies to the pool, so an over-performing team cannot
        # breach it one participant at a time.
        return earned if earned <= self.maximum_pool else self.maximum_pool

    def required_accrual(
        self, achievement: Fraction, year_elapsed: Fraction
    ) -> Money:
        if year_elapsed <= 0 or year_elapsed > 1:
            raise Refused("the elapsed fraction of the year is above zero and at most one")
        return round_money(
            self.earned_pool(achievement).times(year_elapsed),
            self.currency,
            Rounding.HALF_EVEN,
        )

    def movement(self, achievement: Fraction, year_elapsed: Fraction) -> Money:
        return self.required_accrual(achievement, year_elapsed) - self.accrued

    def post(self, achievement: Fraction, year_elapsed: Fraction) -> Money:
        # Recomputed cumulatively, so a collapse late in the year produces a
        # credit rather than a total somebody has to unwind by hand.
        movement = self.movement(achievement, year_elapsed)
        self.accrued = self.required_accrual(achievement, year_elapsed)
        return movement

    def shares(self, achievement: Fraction) -> list[tuple[str, Money]]:
        if not self.participants:
            raise Refused("a bonus pool with no participants funds nothing")
        pool = self.earned_pool(achievement)
        weights = [participant.weight for participant in self.participants]
        amounts = allocate(pool, weights)
        return [
            (participant.name, amount)
            for participant, amount in zip(self.participants, amounts, strict=True)
        ]

    def shares_fund_the_pool(self, achievement: Fraction) -> bool:
        total = Money.zero(self.currency)
        for _, amount in self.shares(achievement):
            total = total + amount
        return total == self.earned_pool(achievement)

    def is_capped(self, achievement: Fraction) -> bool:
        return self.earned_pool(achievement) == self.maximum_pool

    def settle(self, achievement: Fraction) -> Money:
        final = self.earned_pool(achievement)
        difference = final - self.accrued
        self.accrued = final
        return difference
