"""Transfer pricing: what one part of a group may charge another without inventing profit.

When a subsidiary in one country sells to a sister in another, the
price decides which country the profit is taxed in, and a group
left to choose freely would put all of it in the lowest-tax place.
The rule is that the price must be what unrelated parties would
have agreed, the arm's length price, and there are several accepted
ways to work out what that would have been. The comparable
uncontrolled price method uses an actual price from a real
third-party deal, which is the best evidence when it exists. Cost
plus marks up the supplier's cost by the margin a comparable
supplier earns. Resale minus works backward from the price the
buyer eventually sells at, stripping out the margin a comparable
reseller keeps. This module implements the three and, more usefully,
the range test: comparables are never a single number, so an
acceptable price sits inside a range and the module reports whether
a proposed price falls in it and by how far it misses.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money, scale


class Method(Enum):
    COMPARABLE_PRICE = "comparable_uncontrolled_price"
    COST_PLUS = "cost_plus"
    RESALE_MINUS = "resale_minus"


@dataclass(frozen=True)
class ArmsLengthRange:
    low: Money
    high: Money

    def __post_init__(self) -> None:
        self.high.same_currency(self.low)
        if self.high < self.low:
            raise Refused("an arm's length range runs from low to high")

    def contains(self, price: Money) -> bool:
        return self.low <= price <= self.high

    def midpoint(self) -> Money:
        return Money.from_minor(
            (self.low.units + self.high.units) // 2, self.low.currency
        )

    def distance_outside(self, price: Money) -> Money:
        if self.contains(price):
            return Money.zero(price.currency)
        if price < self.low:
            return self.low - price
        return price - self.high


def comparable_price(observed: list[Money]) -> ArmsLengthRange:
    if not observed:
        raise Refused(
            "a comparable price method needs at least one third-party price; "
            "without one there is nothing to compare against"
        )
    currency = observed[0].currency
    for price in observed:
        if price.currency != currency:
            raise Refused("comparable prices are all in one currency")
    return ArmsLengthRange(min(observed), max(observed))


def cost_plus(cost: Money, markup: Fraction) -> Money:
    if markup < 0:
        raise Refused("a cost-plus markup is not negative")
    if not cost.is_positive():
        raise Refused("a cost-plus price starts from a positive cost")
    return cost + scale(cost, markup, Rounding.HALF_EVEN)


def resale_minus(resale_price: Money, gross_margin: Fraction) -> Money:
    if gross_margin < 0 or gross_margin >= 1:
        raise Refused("a resale gross margin is a fraction below one")
    if not resale_price.is_positive():
        raise Refused("a resale-minus price starts from a positive resale price")
    return resale_price - scale(resale_price, gross_margin, Rounding.HALF_EVEN)


@dataclass(frozen=True)
class PricingTest:
    method: Method
    proposed: Money
    acceptable: ArmsLengthRange

    def is_arms_length(self) -> bool:
        return self.acceptable.contains(self.proposed)

    def adjustment(self) -> Money:
        # The amount a tax authority would move the price by: to the nearest
        # edge of the range, not to the midpoint.
        if self.is_arms_length():
            return Money.zero(self.proposed.currency)
        if self.proposed < self.acceptable.low:
            return self.acceptable.low - self.proposed
        return self.acceptable.high - self.proposed

    def verdict(self) -> str:
        if self.is_arms_length():
            return f"within the arm's length range under {self.method.value}"
        missed = self.acceptable.distance_outside(self.proposed)
        return (
            f"outside the arm's length range by {missed.format()} under "
            f"{self.method.value}"
        )


def markup_implied(cost: Money, price: Money) -> Fraction | None:
    if cost.units == 0:
        return None
    price.same_currency(cost)
    return Fraction(price.units - cost.units, cost.units)


def profit_shifted(
    proposed: Money, arms_length: Money, units_sold: int
) -> Money:
    if units_sold < 1:
        raise Refused("profit shifting is measured over at least one unit")
    arms_length.same_currency(proposed)
    per_unit = arms_length - proposed
    return round_money(
        Fraction(per_unit.units * units_sold), proposed.currency, Rounding.HALF_EVEN
    )
