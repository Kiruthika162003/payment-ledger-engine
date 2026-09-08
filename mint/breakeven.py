"""Contribution and break-even: how many units before the fixed costs are covered.

The most useful management number is not profit but contribution,
the selling price less the costs that vary with each unit, because
that is what each additional sale actually contributes toward the
fixed costs and, once those are covered, toward profit. From
contribution everything else follows: the break-even volume is the
fixed costs divided by the contribution per unit, the margin of
safety is how far current sales sit above that point, and the
operating leverage is how violently profit moves when volume does.
This module computes them and is careful about the case that
breaks the arithmetic: a product whose variable cost equals or
exceeds its price has no contribution and therefore no break-even
volume at all, and selling more of it makes the loss larger. That
is refused by name rather than returned as an enormous number,
because an enormous break-even volume reads as a hard target when
the truth is that the target does not exist. Break-even volume
rounds up, since a fraction of a unit does not cover anything.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


@dataclass(frozen=True)
class Product:
    name: str
    price: Money
    variable_cost: Money

    def __post_init__(self) -> None:
        self.variable_cost.same_currency(self.price)
        if not self.price.is_positive():
            raise Refused("a product has a positive price")
        if self.variable_cost.is_negative():
            raise Refused("a variable cost is not negative")

    def contribution(self) -> Money:
        return self.price - self.variable_cost

    def contribution_ratio(self) -> Fraction:
        return Fraction(self.contribution().units, self.price.units)

    def is_viable(self) -> bool:
        return self.contribution().is_positive()


@dataclass(frozen=True)
class BreakEven:
    product: Product
    fixed_costs: Money

    def __post_init__(self) -> None:
        self.fixed_costs.same_currency(self.product.price)
        if self.fixed_costs.is_negative():
            raise Refused("fixed costs are not negative")

    def units_required(self) -> int:
        contribution = self.product.contribution()
        if not contribution.is_positive():
            raise Refused(
                f"{self.product.name!r} contributes nothing per unit, so there "
                "is no break-even volume; selling more makes the loss larger"
            )
        # Rounded up: a fraction of a unit covers nothing.
        return math.ceil(Fraction(self.fixed_costs.units, contribution.units))

    def revenue_required(self) -> Money:
        return Money.from_minor(
            self.units_required() * self.product.price.units, self.product.price.currency
        )

    def profit_at(self, units: int) -> Money:
        if units < 0:
            raise Refused("a volume is not negative")
        contribution = Money.from_minor(
            self.product.contribution().units * units, self.product.price.currency
        )
        return contribution - self.fixed_costs

    def margin_of_safety(self, units: int) -> Fraction | None:
        if units <= 0:
            return None
        required = self.units_required()
        return Fraction(units - required, units)

    def operating_leverage(self, units: int) -> Fraction | None:
        profit = self.profit_at(units)
        if profit.units == 0:
            return None
        contribution = self.product.contribution().units * units
        return Fraction(contribution, profit.units)

    def units_for_target(self, target_profit: Money) -> int:
        target_profit.same_currency(self.fixed_costs)
        contribution = self.product.contribution()
        if not contribution.is_positive():
            raise Refused(
                f"{self.product.name!r} contributes nothing per unit, so no "
                "volume reaches a profit target"
            )
        needed = self.fixed_costs + target_profit
        return math.ceil(Fraction(needed.units, contribution.units))

    def price_for_break_even(self, units: int) -> Money:
        if units < 1:
            raise Refused("a break-even price needs a positive volume")
        needed = Fraction(self.fixed_costs.units, units) + self.product.variable_cost.units
        return round_money(needed, self.product.price.currency, Rounding.CEILING)
