"""Waterfalls: explaining the gap between two numbers as a list of named movements.

When revenue goes from one figure to another, the useful answer is
not the difference but the decomposition: how much came from new
customers, how much from price, how much was lost to churn. A
waterfall is that decomposition, and its one rule is that the
movements must add up: the opening plus every step equals the
closing, exactly, with no residual quietly absorbed into the last
bar. This module enforces that rule rather than trusting it. A
waterfall that does not reconcile is refused when it is built, so a
chart that would silently mislead never gets drawn, and the
unexplained remainder is reported as its own named step when the
caller genuinely cannot attribute it, which is honest in a way that
folding it into another category is not. Steps carry their sign, so
a decline is a negative step rather than a positive one the reader
is expected to know to subtract, and the running total after each
step is available because that is what a chart needs to place each
bar.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mint.errors import Refused
from mint.money import Money

UNEXPLAINED = "unexplained"


@dataclass(frozen=True)
class Step:
    name: str
    amount: Money

    def is_increase(self) -> bool:
        return self.amount.is_positive()


@dataclass
class Waterfall:
    opening: Money
    closing: Money
    steps: list[Step] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.closing.same_currency(self.opening)

    def add(self, name: str, amount: Money) -> Step:
        amount.same_currency(self.opening)
        if not name.strip():
            raise Refused("a waterfall step needs a name")
        step = Step(name.strip(), amount)
        self.steps.append(step)
        return step

    def explained(self) -> Money:
        total = Money.zero(self.opening.currency)
        for step in self.steps:
            total = total + step.amount
        return total

    def residual(self) -> Money:
        return (self.closing - self.opening) - self.explained()

    def reconciles(self) -> bool:
        return self.residual().is_zero()

    def close_with_unexplained(self) -> Step | None:
        gap = self.residual()
        if gap.is_zero():
            return None
        # Named honestly rather than folded into a neighbouring bar.
        return self.add(UNEXPLAINED, gap)

    def running_totals(self) -> list[tuple[str, int]]:
        running = self.opening.units
        rows = [("opening", running)]
        for step in self.steps:
            running += step.amount.units
            rows.append((step.name, running))
        rows.append(("closing", self.closing.units))
        return rows

    def build(self) -> tuple[tuple[str, int], ...]:
        if not self.reconciles():
            raise Refused(
                f"the waterfall leaves {self.residual().format()} unexplained; "
                "name it as a step rather than drawing a chart that misleads"
            )
        return tuple(self.running_totals())

    def largest_step(self) -> Step | None:
        if not self.steps:
            return None
        return max(self.steps, key=lambda step: abs(step.amount.units))

    def increases(self) -> list[Step]:
        return [step for step in self.steps if step.is_increase()]

    def decreases(self) -> list[Step]:
        return [step for step in self.steps if step.amount.is_negative()]
