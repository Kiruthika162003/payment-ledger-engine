"""Surcharges: the extras added after the price, in an order that changes the total.

A surcharge is an amount added to a price for a reason other than
the goods: a fuel levy, a small-order fee, a card fee, a service
charge. They arrive as fixed amounts or percentages, and the
percentages compound if applied in sequence, so a ten percent
service charge followed by a five percent card fee is not the same
as fifteen percent. This module applies surcharges in a stated
order and reports each one's contribution, so the receipt can show
what was added and why rather than a single inflated total. The
base each percentage applies to is explicit: a surcharge may be
computed on the original price or on the running total including
earlier surcharges, and the difference is real money on a large
order. A cap can be set on any surcharge, since many jurisdictions
limit card fees to the merchant's actual cost and an uncapped
percentage on a large order breaks that rule. Surcharges never turn
a price negative because they only add, but a cap of zero
effectively disables one, which is how a promotion waives a fee
without deleting the rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


class SurchargeBase(Enum):
    ORIGINAL = "original"
    RUNNING = "running"


@dataclass(frozen=True)
class Surcharge:
    name: str
    percent: Fraction | None = None
    fixed: Money | None = None
    base: SurchargeBase = SurchargeBase.ORIGINAL
    cap: Money | None = None

    def __post_init__(self) -> None:
        if self.percent is None and self.fixed is None:
            raise Refused(f"surcharge {self.name!r} adds neither a rate nor an amount")
        if self.percent is not None and self.percent < 0:
            raise Refused(f"surcharge {self.name!r} has a negative rate")
        if self.fixed is not None and self.fixed.is_negative():
            raise Refused(f"surcharge {self.name!r} has a negative fixed amount")
        if self.cap is not None and self.cap.is_negative():
            raise Refused(f"surcharge {self.name!r} has a negative cap")

    def amount(self, original: Money, running: Money) -> Money:
        base = original if self.base is SurchargeBase.ORIGINAL else running
        total = Money.zero(base.currency)
        if self.percent is not None:
            total = total + scale(base, self.percent, Rounding.HALF_EVEN)
        if self.fixed is not None:
            self.fixed.same_currency(base)
            total = total + self.fixed
        if self.cap is not None and total > self.cap:
            return self.cap
        return total


@dataclass(frozen=True)
class SurchargeResult:
    original: Money
    lines: tuple[tuple[str, int], ...]
    total: Money

    def added(self) -> Money:
        return self.total - self.original

    def line(self, name: str) -> Money:
        for label, units in self.lines:
            if label == name:
                return Money.from_minor(units, self.original.currency)
        raise Refused(f"no surcharge named {name!r} was applied")


@dataclass
class SurchargeSchedule:
    surcharges: list[Surcharge] = field(default_factory=list)

    def add(self, surcharge: Surcharge) -> Surcharge:
        self.surcharges.append(surcharge)
        return surcharge

    def apply(self, price: Money) -> SurchargeResult:
        running = price
        lines: list[tuple[str, int]] = []
        for surcharge in self.surcharges:
            amount = surcharge.amount(price, running)
            lines.append((surcharge.name, amount.units))
            running = running + amount
        return SurchargeResult(original=price, lines=tuple(lines), total=running)
