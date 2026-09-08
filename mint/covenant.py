"""Loan covenants: the tests a borrower must keep passing, and how close they are to failing.

A loan agreement does not only say when to pay; it says what the
business must look like while the loan is outstanding. Leverage
below a multiple, interest cover above one, a minimum net worth.
Breaching any of them can make the whole loan repayable
immediately, so the number a treasurer wants is not pass or fail
but headroom: how far the metric can move before the test breaks.
This module computes both. Each covenant knows its direction,
whether the metric must stay below a limit or above a floor, which
is what lets headroom be reported as a single signed figure rather
than leaving the reader to work out which way is dangerous. A
covenant whose denominator is zero cannot be tested rather than
being treated as passing, because a business with no earnings has
not passed its interest cover test, it has made the test
meaningless, and reporting that as a pass is how a breach goes
unnoticed until the bank calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money


class Direction(Enum):
    AT_MOST = "at_most"
    AT_LEAST = "at_least"


@dataclass(frozen=True)
class CovenantResult:
    name: str
    measured: Fraction | None
    limit: Fraction
    direction: Direction

    def is_testable(self) -> bool:
        return self.measured is not None

    def passes(self) -> bool:
        if self.measured is None:
            return False
        if self.direction is Direction.AT_MOST:
            return self.measured <= self.limit
        return self.measured >= self.limit

    def headroom(self) -> Fraction | None:
        if self.measured is None:
            return None
        if self.direction is Direction.AT_MOST:
            return self.limit - self.measured
        return self.measured - self.limit

    def verdict(self) -> str:
        if not self.is_testable():
            return (
                f"{self.name} cannot be tested; the measure has no denominator, "
                "which is not the same as passing"
            )
        room = self.headroom()
        if room < 0:
            return f"{self.name} is breached by {abs(room)}"
        return f"{self.name} passes with headroom of {room}"


@dataclass
class CovenantSuite:
    currency: str
    ebitda: Money
    net_debt: Money
    interest_expense: Money
    net_worth: Money
    results: list[CovenantResult] = field(default_factory=list)

    def __post_init__(self) -> None:
        for value in (self.net_debt, self.interest_expense, self.net_worth):
            value.same_currency(self.ebitda)

    def leverage(self) -> Fraction | None:
        if self.ebitda.units <= 0:
            return None
        return Fraction(self.net_debt.units, self.ebitda.units)

    def interest_cover(self) -> Fraction | None:
        if self.interest_expense.units <= 0:
            return None
        return Fraction(self.ebitda.units, self.interest_expense.units)

    def test_leverage(self, limit: Fraction) -> CovenantResult:
        result = CovenantResult("leverage", self.leverage(), limit, Direction.AT_MOST)
        self.results.append(result)
        return result

    def test_interest_cover(self, floor: Fraction) -> CovenantResult:
        result = CovenantResult(
            "interest cover", self.interest_cover(), floor, Direction.AT_LEAST
        )
        self.results.append(result)
        return result

    def test_net_worth(self, floor: Money) -> CovenantResult:
        floor.same_currency(self.net_worth)
        result = CovenantResult(
            "net worth",
            Fraction(self.net_worth.units),
            Fraction(floor.units),
            Direction.AT_LEAST,
        )
        self.results.append(result)
        return result

    def all_pass(self) -> bool:
        return bool(self.results) and all(result.passes() for result in self.results)

    def breaches(self) -> list[CovenantResult]:
        return [result for result in self.results if not result.passes()]

    def untestable(self) -> list[CovenantResult]:
        return [result for result in self.results if not result.is_testable()]

    def tightest(self) -> CovenantResult | None:
        testable = [result for result in self.results if result.is_testable()]
        if not testable:
            return None
        return min(testable, key=lambda result: result.headroom())

    def is_accelerable(self) -> bool:
        # Any breach can make the whole loan repayable at once.
        return bool(self.breaches())


def ebitda_headroom(
    suite: CovenantSuite, leverage_limit: Fraction
) -> Money | None:
    if leverage_limit <= 0:
        raise Refused("a leverage limit is positive")
    required = Fraction(suite.net_debt.units) / leverage_limit
    shortfall = Fraction(suite.ebitda.units) - required
    return Money.from_minor(int(shortfall), suite.currency)
