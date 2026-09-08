"""Share-based pay: a cost measured at grant, spread over vesting, trued up for leavers.

Paying people in options is not free, and the accounting exists to
say so. The cost is the fair value of the award at the date it was
granted, and it is recognized across the period the employee has to
work to earn it rather than when the options are exercised, because
the service is what the company is paying for. Two things then make
it awkward. Employees leave before vesting, so the expense is
recognized on the number expected to vest and trued up as reality
arrives, which means the cumulative charge is recomputed each
period rather than the increment being estimated afresh. And a
market condition, such as a share price target, is baked into the
grant-date value and never trued up, while a service condition is,
which is the distinction most implementations miss. This module
recomputes cumulative cost every period and reports the movement,
so a wave of leavers produces a credit rather than a silently wrong
running total.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


@dataclass
class ShareAward:
    id: str
    grant_date_fair_value: Money
    options_granted: int
    vesting_periods: int
    expected_to_vest: int | None = None
    periods_elapsed: int = 0
    recognized: Money | None = None
    forfeited: int = 0

    def __post_init__(self) -> None:
        if not self.grant_date_fair_value.is_positive():
            raise Refused("an award has a positive grant-date fair value per option")
        if self.options_granted < 1:
            raise Refused("an award grants at least one option")
        if self.vesting_periods < 1:
            raise Refused("an award vests over at least one period")
        if self.expected_to_vest is None:
            self.expected_to_vest = self.options_granted
        if self.recognized is None:
            self.recognized = Money.zero(self.grant_date_fair_value.currency)

    def total_expected_cost(self) -> Money:
        return Money.from_minor(
            self.grant_date_fair_value.units * self.expected_to_vest,
            self.grant_date_fair_value.currency,
        )

    def vested_fraction(self) -> Fraction:
        return Fraction(min(self.periods_elapsed, self.vesting_periods), self.vesting_periods)

    def cumulative_cost(self) -> Money:
        # Recomputed from scratch each period, which is what makes the
        # true-up work when the expectation changes.
        return round_money(
            self.total_expected_cost().times(self.vested_fraction()),
            self.grant_date_fair_value.currency,
            Rounding.HALF_EVEN,
        )

    def advance_period(self) -> Money:
        if self.is_fully_vested():
            raise Refused(f"award {self.id!r} has fully vested")
        self.periods_elapsed += 1
        return self.post()

    def post(self) -> Money:
        movement = self.cumulative_cost() - self.recognized
        self.recognized = self.cumulative_cost()
        return movement

    def revise_expectation(self, expected: int) -> Money:
        if expected < 0 or expected > self.options_granted:
            raise Refused(
                "the number expected to vest lies between zero and the number "
                "granted"
            )
        self.expected_to_vest = expected
        return self.post()

    def forfeit(self, options: int) -> Money:
        if options < 1:
            raise Refused("a forfeiture covers at least one option")
        if self.forfeited + options > self.options_granted:
            raise Refused("more options forfeited than were ever granted")
        self.forfeited += options
        return self.revise_expectation(self.options_granted - self.forfeited)

    def is_fully_vested(self) -> bool:
        return self.periods_elapsed >= self.vesting_periods

    def cost_per_period(self) -> Money:
        return round_money(
            Fraction(self.total_expected_cost().units, self.vesting_periods),
            self.grant_date_fair_value.currency,
            Rounding.HALF_EVEN,
        )


@dataclass
class MarketConditionAward(ShareAward):
    """An award whose condition is a share price target rather than service.

    The distinction most implementations miss: a market condition is
    priced into the grant-date fair value and never trued up, so the
    cost stands whether or not the target is met, while a service
    condition is trued up as leavers arrive.
    """

    def revise_expectation(self, _expected: int) -> Money:
        # The argument is deliberately ignored: there is no expectation to
        # revise on a market condition, whatever number is offered.
        raise Refused(
            f"award {self.id!r} carries a market condition, which is priced "
            "into the grant-date value and never trued up"
        )

    def forfeit(self, _options: int) -> Money:
        raise Refused(
            f"award {self.id!r} carries a market condition; failing the target "
            "does not reverse the cost"
        )


@dataclass
class CompensationPlan:
    currency: str
    awards: list[ShareAward] = field(default_factory=list)

    def add(self, award: ShareAward) -> ShareAward:
        if award.grant_date_fair_value.currency != self.currency:
            raise Refused(
                f"award {award.id!r} is priced in "
                f"{award.grant_date_fair_value.currency}, not {self.currency}"
            )
        self.awards.append(award)
        return award

    def total_recognized(self) -> Money:
        total = Money.zero(self.currency)
        for award in self.awards:
            total = total + award.recognized
        return total

    def total_expected(self) -> Money:
        total = Money.zero(self.currency)
        for award in self.awards:
            total = total + award.total_expected_cost()
        return total

    def unrecognized(self) -> Money:
        return self.total_expected() - self.total_recognized()
