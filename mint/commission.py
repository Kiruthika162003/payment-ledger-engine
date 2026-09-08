"""Sales commission: earning it on the sale, and losing it when the sale unwinds.

Commission looks like a percentage and behaves like a small
accounting system, because the events that follow a sale change
what was earned. A refunded order should claw back the commission
paid on it, or the company pays a salesperson for revenue it never
kept; an unpaid invoice may or may not be commissionable depending
on whether the plan pays on booking or on collection. This module
implements both bases and the clawback. Rates are graduated across
attainment tiers, the common structure where the rate rises once a
quota is passed, and the earned amount is computed on cumulative
attainment rather than per deal, because computing each deal at the
rate current when it closed produces a different total depending on
the order the deals are processed, which is the bug that makes two
runs of the same month disagree. A split between several
salespeople on one deal uses the cent-conserving allocation, so the
sum of the splits equals the commission on the deal exactly rather
than drifting by a cent that has to be absorbed somewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, allocate, scale


class CommissionBasis(Enum):
    ON_BOOKING = "on_booking"
    ON_COLLECTION = "on_collection"


@dataclass(frozen=True)
class AttainmentTier:
    above: Money
    rate: Fraction

    def __post_init__(self) -> None:
        if self.rate < 0 or self.rate >= 1:
            raise Refused("a commission rate is a fraction below one")


@dataclass
class CommissionPlan:
    currency: str
    tiers: tuple[AttainmentTier, ...]
    basis: CommissionBasis = CommissionBasis.ON_BOOKING

    def __post_init__(self) -> None:
        if not self.tiers:
            raise Refused("a commission plan needs at least one tier")
        if self.tiers[0].above.units != 0:
            raise Refused("the first commission tier starts at zero attainment")
        bounds = [tier.above.units for tier in self.tiers]
        if bounds != sorted(bounds) or len(set(bounds)) != len(bounds):
            raise Refused("commission tiers must strictly increase")

    def commission_on(self, attainment: Money) -> Money:
        # Graduated on cumulative attainment, so the total never depends on
        # the order the deals happened to be processed in.
        total = Money.zero(self.currency)
        remaining = attainment.units
        for index, tier in enumerate(self.tiers):
            floor = tier.above.units
            ceiling = (
                self.tiers[index + 1].above.units
                if index + 1 < len(self.tiers)
                else None
            )
            if remaining <= floor:
                break
            top = remaining if ceiling is None else min(ceiling, remaining)
            slice_units = top - floor
            if slice_units <= 0:
                continue
            total = total + scale(
                Money.from_minor(slice_units, self.currency), tier.rate,
                Rounding.HALF_EVEN,
            )
        return total


@dataclass
class CommissionLedger:
    plan: CommissionPlan
    booked: Money | None = None
    collected: Money | None = None
    refunded: Money | None = None
    paid_out: Money | None = None
    deals: list[tuple[str, Money]] = field(default_factory=list)

    def __post_init__(self) -> None:
        zero = Money.zero(self.plan.currency)
        self.booked = self.booked or zero
        self.collected = self.collected or zero
        self.refunded = self.refunded or zero
        self.paid_out = self.paid_out or zero

    def book(self, deal_id: str, amount: Money) -> Money:
        self._guard(amount)
        self.booked = self.booked + amount
        self.deals.append((deal_id, amount))
        return self.booked

    def collect(self, amount: Money) -> Money:
        self._guard(amount)
        self.collected = self.collected + amount
        return self.collected

    def refund(self, amount: Money) -> Money:
        self._guard(amount)
        self.refunded = self.refunded + amount
        return self.refunded

    def attainment(self) -> Money:
        base = (
            self.booked
            if self.plan.basis is CommissionBasis.ON_BOOKING
            else self.collected
        )
        return base - self.refunded

    def earned(self) -> Money:
        return self.plan.commission_on(self.attainment())

    def payable(self) -> Money:
        return self.earned() - self.paid_out

    def pay(self) -> Money:
        movement = self.payable()
        self.paid_out = self.earned()
        return movement

    def _guard(self, amount: Money) -> None:
        if amount.currency != self.plan.currency:
            raise Refused(
                f"this plan is in {self.plan.currency}, not {amount.currency}"
            )
        if not amount.is_positive():
            raise Refused("a commission movement is a positive amount")


def split_commission(total: Money, weights: list[int]) -> list[Money]:
    if not weights:
        raise Refused("a commission split needs at least one participant")
    return allocate(total, [Fraction(w) for w in weights])
