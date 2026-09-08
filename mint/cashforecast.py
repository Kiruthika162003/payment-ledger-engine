"""The short-term cash forecast: week by week, and the week it runs out.

The forecast a business in difficulty actually runs is not annual,
it is thirteen weeks, because that is the horizon over which cash
can be managed and beyond which the numbers are guesses. It is
built from receipts and payments in the weeks they will land, not
the weeks they were earned or incurred, which is the whole
difference between a cash forecast and a profit forecast and the
reason a profitable business can be about to fail. This module
projects the balance week by week and reports the first week it
goes negative, which is the single number the exercise exists to
produce; it also reports the lowest point, since a business that
dips and recovers still needs to fund the dip. Receipts can be
weighted by a collection probability, because a forecast that
counts every invoice as certain to be paid on the day it is due is
not a forecast, it is a wish, and the module keeps the weighted and
unweighted views separate so the optimism is visible rather than
baked in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


@dataclass(frozen=True)
class Flow:
    week: int
    description: str
    amount: Money
    probability: Fraction = Fraction(1)

    def __post_init__(self) -> None:
        if self.week < 1:
            raise Refused("a forecast week is numbered from one")
        if self.probability <= 0 or self.probability > 1:
            raise Refused(
                "a collection probability is above zero and at most one"
            )

    def weighted(self) -> Money:
        return scale(self.amount, self.probability, Rounding.HALF_EVEN)


@dataclass
class CashForecast:
    currency: str
    opening: Money
    weeks: int = 13
    flows: list[Flow] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.opening.same_currency(Money.zero(self.currency))
        if self.weeks < 1:
            raise Refused("a forecast covers at least one week")

    def add_receipt(
        self, week: int, description: str, amount: Money,
        probability: Fraction = Fraction(1),
    ) -> Flow:
        return self._add(week, description, amount, probability, inflow=True)

    def add_payment(self, week: int, description: str, amount: Money) -> Flow:
        return self._add(week, description, amount, Fraction(1), inflow=False)

    def _add(
        self, week: int, description: str, amount: Money,
        probability: Fraction, inflow: bool,
    ) -> Flow:
        if amount.currency != self.currency:
            raise Refused(
                f"a {amount.currency} flow does not belong in a "
                f"{self.currency} forecast"
            )
        if not amount.is_positive():
            raise Refused("a forecast flow is a positive amount; its side sets the sign")
        if week > self.weeks:
            raise Refused(
                f"week {week} is beyond the {self.weeks}-week horizon; past that "
                "the numbers are guesses rather than a forecast"
            )
        flow = Flow(week, description, amount if inflow else -amount, probability)
        self.flows.append(flow)
        return flow

    def balances(self, weighted: bool = True) -> list[Money]:
        running = self.opening
        out: list[Money] = []
        for week in range(1, self.weeks + 1):
            for flow in self.flows:
                if flow.week != week:
                    continue
                running = running + (flow.weighted() if weighted else flow.amount)
            out.append(running)
        return out

    def closing(self, weighted: bool = True) -> Money:
        return self.balances(weighted)[-1]

    def first_negative_week(self, weighted: bool = True) -> int | None:
        for index, balance in enumerate(self.balances(weighted), start=1):
            if balance.is_negative():
                return index
        return None

    def lowest_point(self, weighted: bool = True) -> Money:
        # A business that dips and recovers still has to fund the dip.
        return min(self.balances(weighted), key=lambda money: money.units)

    def survives(self, weighted: bool = True) -> bool:
        return self.first_negative_week(weighted) is None

    def optimism_gap(self) -> Money:
        return self.closing(weighted=False) - self.closing(weighted=True)

    def shortfall_to_fund(self, weighted: bool = True) -> Money:
        low = self.lowest_point(weighted)
        return -low if low.is_negative() else Money.zero(self.currency)
