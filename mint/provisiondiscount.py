"""Discounting a long-term provision, and the interest that unwinds it back up.

A cost that will be paid in ten years is not worth ten years' worth
of money today, so a long-term provision is carried at the present
value of the expected outflow rather than the outflow itself. That
creates an obligation that grows every year even though nothing has
changed, because it is one year closer, and the growth is the
unwinding of the discount. The unwinding is a finance cost rather
than an operating one, which matters because burying it in the
operating line makes the operations look worse than they are and
the interest cost look smaller. This module carries the provision at
present value, unwinds it period by period, and confirms the
property that makes the whole approach coherent: after the full
term the carrying amount has grown to exactly the undiscounted
amount, so nothing is created or lost by discounting. A change in
the estimate or the rate remeasures the provision, and the module
reports that separately from the unwinding, because the two have
different causes and belong on different lines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


@dataclass(frozen=True)
class UnwindStep:
    period: int
    opening: int
    finance_cost: int
    closing: int


@dataclass
class DiscountedProvision:
    id: str
    undiscounted: Money
    rate: Fraction
    periods: int
    carrying: Money | None = None
    elapsed: int = 0
    steps: list[UnwindStep] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.undiscounted.is_positive():
            raise Refused("a provision is for a positive expected outflow")
        if self.rate < 0:
            raise Refused("a discount rate is not negative")
        if self.periods < 1:
            raise Refused("a discounted provision runs for at least one period")
        if self.carrying is None:
            self.carrying = self.present_value()

    def present_value(self) -> Money:
        factor = (1 + self.rate) ** self.periods
        return round_money(
            Fraction(self.undiscounted.units) / factor,
            self.undiscounted.currency,
            Rounding.HALF_EVEN,
        )

    def discount_taken(self) -> Money:
        return self.undiscounted - self.present_value()

    def remaining_periods(self) -> int:
        return max(0, self.periods - self.elapsed)

    def unwind(self) -> Money:
        if self.elapsed >= self.periods:
            raise Refused(f"provision {self.id!r} has fully unwound")
        opening = self.carrying.units
        self.elapsed += 1
        if self.elapsed == self.periods:
            # The last step lands exactly on the undiscounted amount, so
            # discounting neither creates nor loses money over the term.
            closing = self.undiscounted.units
        else:
            grown = round_money(
                self.carrying.times(1 + self.rate),
                self.undiscounted.currency,
                Rounding.HALF_EVEN,
            )
            closing = grown.units
        cost = closing - opening
        self.carrying = Money.from_minor(closing, self.undiscounted.currency)
        self.steps.append(UnwindStep(self.elapsed, opening, cost, closing))
        return Money.from_minor(cost, self.undiscounted.currency)

    def unwind_fully(self) -> Money:
        total = Money.zero(self.undiscounted.currency)
        while self.elapsed < self.periods:
            total = total + self.unwind()
        return total

    def is_fully_unwound(self) -> bool:
        return self.elapsed >= self.periods

    def lands_on_the_outflow(self) -> bool:
        return self.is_fully_unwound() and self.carrying == self.undiscounted

    def remeasure(
        self, undiscounted: Money | None = None, rate: Fraction | None = None
    ) -> Money:
        # Reported apart from the unwinding: a changed estimate and the
        # passage of time have different causes and different lines.
        if undiscounted is not None:
            undiscounted.same_currency(self.undiscounted)
            if not undiscounted.is_positive():
                raise Refused("a remeasured provision stays positive")
            self.undiscounted = undiscounted
        if rate is not None:
            if rate < 0:
                raise Refused("a discount rate is not negative")
            self.rate = rate
        before = self.carrying
        factor = (1 + self.rate) ** self.remaining_periods()
        self.carrying = round_money(
            Fraction(self.undiscounted.units) / factor,
            self.undiscounted.currency,
            Rounding.HALF_EVEN,
        )
        return self.carrying - before

    def total_finance_cost(self) -> Money:
        return Money.from_minor(
            sum(step.finance_cost for step in self.steps),
            self.undiscounted.currency,
        )
