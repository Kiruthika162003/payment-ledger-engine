"""Tiered pricing: the two models that look alike and charge very differently.

There are two ways to price by volume and confusing them is a
classic billing bug. Graduated pricing charges each unit at the
rate of the tier it falls in, so with the first hundred at ten
cents and the rest at five, a hundred and fifty units cost ten
dollars plus two fifty. Volume pricing charges every unit at the
rate of the tier the total lands in, so the same hundred and fifty
units cost seven fifty, all at the higher-tier rate. Both are
legitimate and customers sign contracts for each, but a system
that implements one while the contract says the other overbills or
underbills every invoice, and the error is invisible because both
produce plausible numbers. This module implements both explicitly,
named, so the choice is made at the call site rather than by
whichever loop someone wrote first. Tiers must start at zero and
increase without gaps, since a gap leaves quantities with no price
at all, and the last tier is open-ended because there is always a
customer larger than the table anticipated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


class PricingModel(Enum):
    GRADUATED = "graduated"
    VOLUME = "volume"
    FLAT = "flat"


@dataclass(frozen=True)
class Tier:
    up_to: int | None
    unit_price: Money

    def __post_init__(self) -> None:
        if self.up_to is not None and self.up_to < 1:
            raise Refused("a tier's upper bound is at least one unit")
        if self.unit_price.is_negative():
            raise Refused("a tier price is not negative")


@dataclass(frozen=True)
class PriceTable:
    tiers: tuple[Tier, ...]
    model: PricingModel

    def __post_init__(self) -> None:
        if not self.tiers:
            raise Refused("a price table needs at least one tier")
        bounds = [tier.up_to for tier in self.tiers]
        if any(bound is None for bound in bounds[:-1]):
            raise Refused("only the last tier may be open-ended")
        if bounds[-1] is not None:
            raise Refused(
                "the last tier must be open-ended; there is always a customer "
                "larger than the table anticipated"
            )
        finite = list(bounds[:-1])
        if finite != sorted(finite) or len(set(finite)) != len(finite):
            raise Refused("tier bounds must strictly increase without repeats")

    def currency(self) -> str:
        return self.tiers[0].unit_price.currency

    def tier_for(self, quantity: int) -> Tier:
        for tier in self.tiers:
            if tier.up_to is None or quantity <= tier.up_to:
                return tier
        return self.tiers[-1]

    def price(self, quantity: int) -> Money:
        if quantity < 0:
            raise Refused("a priced quantity is not negative")
        if quantity == 0:
            return Money.zero(self.currency())
        if self.model is PricingModel.VOLUME:
            tier = self.tier_for(quantity)
            return round_money(
                tier.unit_price.times(quantity), self.currency(), Rounding.HALF_EVEN
            )
        if self.model is PricingModel.FLAT:
            return self.tiers[0].unit_price
        return self._graduated(quantity)

    def _graduated(self, quantity: int) -> Money:
        total = Money.zero(self.currency())
        consumed = 0
        for tier in self.tiers:
            if consumed >= quantity:
                break
            ceiling = quantity if tier.up_to is None else min(tier.up_to, quantity)
            units = ceiling - consumed
            if units <= 0:
                continue
            total = total + round_money(
                tier.unit_price.times(units), self.currency(), Rounding.HALF_EVEN
            )
            consumed = ceiling
        return total

    def effective_unit_price(self, quantity: int) -> Fraction | None:
        if quantity <= 0:
            return None
        return Fraction(self.price(quantity).units, quantity)
