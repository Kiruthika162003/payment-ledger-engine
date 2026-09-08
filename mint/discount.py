"""Discounts: percentage and fixed, applied in order, never below zero.

A discount reduces an amount, and the two kinds compose in an
order that changes the answer, so this module makes the order
explicit rather than leaving it to whichever loop ran first. A
percentage discount takes a fraction of the current amount; a
fixed discount subtracts a stated sum. Ten percent then five
dollars off a hundred is not the same as five dollars then ten
percent off, and a checkout that silently picks one has silently
picked a price, so discounts are applied in the sequence given and
the sequence is part of the input. No discount drives an amount
below zero, because a coupon larger than the cart is a coupon
capped at the cart, not a store paying the customer to leave; the
excess is dropped rather than turned into a negative price. The
result reports the original, the final, and the total taken off, so
a receipt can show the saving as a line rather than leaving the
customer to subtract, and every figure is money in whole minor
units so the discount reconciles against the price to the cent.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


class DiscountKind(Enum):
    PERCENT = "percent"
    FIXED = "fixed"


@dataclass(frozen=True)
class Discount:
    kind: DiscountKind
    name: str
    percent: Fraction | None = None
    fixed: Money | None = None

    @classmethod
    def of_percent(cls, fraction: Fraction, name: str) -> Discount:
        if fraction < 0 or fraction > 1:
            raise Refused("a percentage discount is a fraction between zero and one")
        return cls(DiscountKind.PERCENT, name, percent=fraction)

    @classmethod
    def of_fixed(cls, amount: Money, name: str) -> Discount:
        if amount.is_negative():
            raise Refused("a fixed discount is not negative")
        return cls(DiscountKind.FIXED, name, fixed=amount)

    def reduction(self, amount: Money) -> Money:
        if self.kind is DiscountKind.PERCENT:
            return scale(amount, self.percent, Rounding.HALF_EVEN)
        self.fixed.same_currency(amount)
        return self.fixed if self.fixed <= amount else amount


@dataclass(frozen=True)
class DiscountResult:
    original: Money
    final: Money
    steps: tuple[tuple[str, int], ...]

    def total_discount(self) -> Money:
        return self.original - self.final


def apply_discounts(amount: Money, discounts: list[Discount]) -> DiscountResult:
    running = amount
    steps: list[tuple[str, int]] = []
    for discount in discounts:
        cut = discount.reduction(running)
        cut = min(cut, running)
        running = running - cut
        steps.append((discount.name, cut.units))
    return DiscountResult(original=amount, final=running, steps=tuple(steps))
