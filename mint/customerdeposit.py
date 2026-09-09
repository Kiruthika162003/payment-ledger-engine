"""Security deposits: somebody else's money that you are holding, not money you earned.

A security deposit is a liability from the moment it is taken. The
tenant or customer still owns it, the business is merely holding
it, and treating it as income is the single most common way small
businesses spend money they will have to give back. This module
holds deposits as liabilities and returns them, applying deductions
only for stated reasons, since an unexplained deduction is the
dispute that costs more than the deposit. In many places the holder
must pay interest on the deposit, so interest accrues to the
depositor rather than to the holder and is added to what must be
returned. The return is computed as the deposit plus interest less
itemized deductions, and if the deductions exceed the deposit the
excess is reported as separately recoverable rather than netted to
zero, because a business owed more than it holds still has a claim
and pretending otherwise writes it off silently.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from fractions import Fraction

from mint.daycount import DayCount, year_fraction
from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


@dataclass(frozen=True)
class Deduction:
    date: datetime.date
    amount: Money
    reason: str


@dataclass(frozen=True)
class ReturnStatement:
    deposit: Money
    interest: Money
    deductions: Money
    returned: Money
    still_recoverable: Money

    def reconciles(self) -> bool:
        owed = self.deposit + self.interest
        return self.returned + self.deductions - self.still_recoverable == owed


@dataclass
class SecurityDeposit:
    id: str
    depositor: str
    amount: Money
    taken_on: datetime.date
    interest_rate: Fraction = Fraction(0)
    convention: DayCount = DayCount.ACT_365F
    deductions: list[Deduction] = field(default_factory=list)
    returned_on: datetime.date | None = None

    def __post_init__(self) -> None:
        if not self.amount.is_positive():
            raise Refused("a deposit holds a positive amount")
        if self.interest_rate < 0:
            raise Refused("a deposit interest rate is not negative")

    def is_returned(self) -> bool:
        return self.returned_on is not None

    def interest_to(self, as_of: datetime.date) -> Money:
        # Accrues to the depositor, not to the holder: it was never the
        # holder's money to earn on.
        if as_of <= self.taken_on or self.interest_rate == 0:
            return Money.zero(self.amount.currency)
        fraction = year_fraction(self.taken_on, as_of, self.convention)
        return round_money(
            self.amount.times(self.interest_rate * fraction),
            self.amount.currency,
            Rounding.HALF_EVEN,
        )

    def liability_at(self, as_of: datetime.date) -> Money:
        return self.amount + self.interest_to(as_of)

    def deduct(self, amount: Money, on: datetime.date, reason: str) -> Deduction:
        amount.same_currency(self.amount)
        if self.is_returned():
            raise Refused(f"deposit {self.id!r} has already been returned")
        if not amount.is_positive():
            raise Refused("a deduction is for a positive amount")
        if not reason.strip():
            raise Refused(
                "a deduction needs a stated reason; an unexplained one is the "
                "dispute that costs more than the deposit"
            )
        deduction = Deduction(on, amount, reason.strip())
        self.deductions.append(deduction)
        return deduction

    def deductions_total(self) -> Money:
        total = Money.zero(self.amount.currency)
        for deduction in self.deductions:
            total = total + deduction.amount
        return total

    def statement(self, as_of: datetime.date) -> ReturnStatement:
        interest = self.interest_to(as_of)
        owed = self.amount + interest
        taken = self.deductions_total()
        if taken > owed:
            # The excess is a live claim, not something to write off quietly.
            return ReturnStatement(
                deposit=self.amount,
                interest=interest,
                deductions=taken,
                returned=Money.zero(self.amount.currency),
                still_recoverable=taken - owed,
            )
        return ReturnStatement(
            deposit=self.amount,
            interest=interest,
            deductions=taken,
            returned=owed - taken,
            still_recoverable=Money.zero(self.amount.currency),
        )

    def give_back(self, on: datetime.date) -> ReturnStatement:
        if self.is_returned():
            raise Refused(f"deposit {self.id!r} has already been returned")
        statement = self.statement(on)
        self.returned_on = on
        return statement


@dataclass
class DepositBook:
    currency: str
    deposits: list[SecurityDeposit] = field(default_factory=list)

    def take(self, deposit: SecurityDeposit) -> SecurityDeposit:
        if deposit.amount.currency != self.currency:
            raise Refused(
                f"deposit {deposit.id!r} is in {deposit.amount.currency}, not "
                f"{self.currency}"
            )
        if any(existing.id == deposit.id for existing in self.deposits):
            raise Refused(f"deposit {deposit.id!r} is already held")
        self.deposits.append(deposit)
        return deposit

    def total_held(self, as_of: datetime.date) -> Money:
        total = Money.zero(self.currency)
        for deposit in self.deposits:
            if not deposit.is_returned():
                total = total + deposit.liability_at(as_of)
        return total

    def outstanding(self) -> list[SecurityDeposit]:
        return [item for item in self.deposits if not item.is_returned()]
