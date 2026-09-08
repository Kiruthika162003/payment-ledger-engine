"""Budget versus actual: the variance, and which direction is the good one.

A variance report subtracts what happened from what was planned,
and the trap is the sign. An expense account that came in under
budget is a favorable variance; a revenue account that came in
under budget is unfavorable, and the same arithmetic produces both,
so a report that prints raw differences without knowing the account
type will color half of them wrong. This module carries the
direction with each budget line and reports the variance both as a
signed amount and as a plain verdict, favorable or unfavorable, so
the reader is not asked to remember which way this particular
account points. Percentage variance is offered against the budget
rather than the actual, since the question is how far off the plan
was rather than how large the plan was relative to reality, and a
line budgeted at zero has no meaningful percentage at all and
returns nothing rather than dividing by zero. Lines are summed to a
total variance that keeps the same signed convention, so the report
foots to a single figure a manager can act on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money


class Direction(Enum):
    # More is better for revenue; less is better for expense.
    MORE_IS_BETTER = "more_is_better"
    LESS_IS_BETTER = "less_is_better"


@dataclass(frozen=True)
class BudgetLine:
    code: str
    name: str
    budget: Money
    actual: Money
    direction: Direction

    def __post_init__(self) -> None:
        self.actual.same_currency(self.budget)

    def variance(self) -> Money:
        return self.actual - self.budget

    def is_favorable(self) -> bool:
        difference = self.variance().units
        if self.direction is Direction.MORE_IS_BETTER:
            return difference >= 0
        return difference <= 0

    def verdict(self) -> str:
        if self.variance().is_zero():
            return "on budget"
        return "favorable" if self.is_favorable() else "unfavorable"

    def percent_of_budget(self) -> Fraction | None:
        if self.budget.units == 0:
            return None
        return Fraction(self.variance().units, self.budget.units)


@dataclass
class BudgetReport:
    currency: str
    lines: list[BudgetLine] = field(default_factory=list)

    def add(
        self,
        code: str,
        name: str,
        budget: Money,
        actual: Money,
        direction: Direction,
    ) -> BudgetLine:
        if budget.currency != self.currency:
            raise Refused(
                f"line {code!r} is budgeted in {budget.currency}, not the "
                f"report currency {self.currency}"
            )
        line = BudgetLine(code, name, budget, actual, direction)
        self.lines.append(line)
        return line

    def total_budget(self) -> Money:
        total = Money.zero(self.currency)
        for line in self.lines:
            total = total + line.budget
        return total

    def total_actual(self) -> Money:
        total = Money.zero(self.currency)
        for line in self.lines:
            total = total + line.actual
        return total

    def total_variance(self) -> Money:
        return self.total_actual() - self.total_budget()

    def unfavorable(self) -> list[BudgetLine]:
        return [line for line in self.lines if not line.is_favorable()]

    def worst_line(self) -> BudgetLine | None:
        offenders = self.unfavorable()
        if not offenders:
            return None
        return max(offenders, key=lambda line: abs(line.variance().units))
