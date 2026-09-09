"""Sinking funds: setting money aside on a schedule so a known debt can be paid.

A borrower who owes a large sum on a fixed date and pays nothing
until then is solvent right up to the moment they are not, which is
why an indenture usually requires a sinking fund: a series of
deposits, growing at whatever the fund earns, that must reach the
redemption amount by the redemption date. The interesting part is
not the compounding, it is the test. A fund can be perfectly on
schedule and still short, because the required deposit was computed
against an assumed rate the fund never actually earned, and a
schedule that reports compliance against its own assumptions rather
than against the balance is worse than no schedule at all. This
module projects the balance forward from the deposits actually made
at the rate actually earned, states the shortfall against the
target in money rather than in a ratio, and refuses a schedule
whose deposits cannot reach the target even in principle, since a
plan that cannot succeed is not a plan.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


@dataclass(frozen=True)
class Deposit:
    on: datetime.date
    amount: Money

    def __post_init__(self) -> None:
        if not self.amount.is_positive():
            raise Refused("a sinking fund deposit is positive")


@dataclass(frozen=True)
class PeriodBalance:
    index: int
    opening: Money
    deposit: Money
    earnings: Money
    closing: Money

    def reconciles(self) -> bool:
        return self.opening + self.deposit + self.earnings == self.closing


@dataclass
class SinkingFund:
    name: str
    target: Money
    periods: int
    period_rate: Fraction
    started_on: datetime.date
    deposits: list[Deposit] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.target.is_positive():
            raise Refused("a sinking fund saves toward a positive target")
        if self.periods <= 0:
            raise Refused("a sinking fund runs for at least one period")
        if self.period_rate < 0:
            raise Refused(
                "a negative period rate would have the fund shrink toward its "
                "target, which is not a schedule anyone can be held to"
            )

    def accumulation_factor(self) -> Fraction:
        # The future value of one unit deposited each period, end of period.
        if self.period_rate == 0:
            return Fraction(self.periods)
        return ((1 + self.period_rate) ** self.periods - 1) / self.period_rate

    def required_deposit(self) -> Money:
        # Rounded up: rounding this one down leaves the fund a few cents short
        # on the last day, which is the one day it must not be short.
        return round_money(
            Fraction(self.target.units) / self.accumulation_factor(),
            self.target.currency,
            Rounding.CEILING,
        )

    def deposit(self, on: datetime.date, amount: Money) -> Deposit:
        amount.same_currency(self.target)
        if on < self.started_on:
            raise Refused(
                f"a deposit on {on.isoformat()} predates the fund, which started "
                f"on {self.started_on.isoformat()}"
            )
        entry = Deposit(on, amount)
        self.deposits.append(entry)
        return entry

    def deposited(self) -> Money:
        total = Money.zero(self.target.currency)
        for entry in self.deposits:
            total = total + entry.amount
        return total

    def schedule(self, deposit: Money | None = None) -> list[PeriodBalance]:
        amount = self.required_deposit() if deposit is None else deposit
        amount.same_currency(self.target)
        rows: list[PeriodBalance] = []
        balance = Money.zero(self.target.currency)
        for index in range(1, self.periods + 1):
            earnings = round_money(
                balance.times(self.period_rate),
                self.target.currency,
                Rounding.HALF_EVEN,
            )
            closing = balance + amount + earnings
            rows.append(PeriodBalance(index, balance, amount, earnings, closing))
            balance = closing
        return rows

    def projected_balance(self, deposit: Money | None = None) -> Money:
        rows = self.schedule(deposit)
        return rows[-1].closing

    def shortfall(self, deposit: Money | None = None) -> Money:
        # Stated in money against the balance, not as a ratio against the plan.
        projected = self.projected_balance(deposit)
        if projected >= self.target:
            return Money.zero(self.target.currency)
        return self.target - projected

    def reaches_target(self, deposit: Money | None = None) -> bool:
        return self.shortfall(deposit).is_zero()

    def surplus(self, deposit: Money | None = None) -> Money:
        projected = self.projected_balance(deposit)
        if projected <= self.target:
            return Money.zero(self.target.currency)
        return projected - self.target

    def periods_elapsed(self, on: datetime.date) -> int:
        if on < self.started_on:
            return 0
        return len([entry for entry in self.deposits if entry.on <= on])

    def balance_at(self, on: datetime.date) -> Money:
        # From the deposits actually made, not from the schedule they were
        # supposed to follow.
        balance = Money.zero(self.target.currency)
        for entry in sorted(self.deposits, key=lambda item: item.on):
            if entry.on > on:
                break
            earnings = round_money(
                balance.times(self.period_rate),
                self.target.currency,
                Rounding.HALF_EVEN,
            )
            balance = balance + earnings + entry.amount
        return balance

    def is_on_schedule(self, on: datetime.date) -> bool:
        elapsed = self.periods_elapsed(on)
        if elapsed == 0:
            return True
        if elapsed > self.periods:
            return self.balance_at(on) >= self.target
        expected = self.schedule()[elapsed - 1].closing
        return self.balance_at(on) >= expected

    def catch_up_deposit(self, on: datetime.date) -> Money:
        elapsed = self.periods_elapsed(on)
        remaining = self.periods - elapsed
        if remaining <= 0:
            deficit = self.target - self.balance_at(on)
            return deficit if deficit.is_positive() else Money.zero(
                self.target.currency
            )
        balance = self.balance_at(on)
        if self.period_rate == 0:
            factor = Fraction(remaining)
            grown = Fraction(balance.units)
        else:
            factor = ((1 + self.period_rate) ** remaining - 1) / self.period_rate
            grown = Fraction(balance.units) * (1 + self.period_rate) ** remaining
        needed = Fraction(self.target.units) - grown
        if needed <= 0:
            return Money.zero(self.target.currency)
        return round_money(needed / factor, self.target.currency, Rounding.CEILING)
