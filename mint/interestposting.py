"""Posting interest: accruing daily, capitalizing monthly, and never twice for a day.

Interest is earned every day and posted much less often, so the
machinery between the two is where interest gets lost or doubled. A
run that posts accrued interest must know exactly which days it has
already covered, or a job that runs twice pays twice and a job that
skips a day pays nothing for it. This module tracks the last day
posted through and accrues only from there, so re-running a
posting is a no-op rather than a duplicate, which is the property
that lets an operator retry a failed batch without arithmetic
anxiety. Accrual is computed per day on that day's balance rather
than on an average, since a balance that moved mid-period earns
differently from one that sat still, and the daily figures are
summed exactly before a single rounding at posting time. Interest
capitalizes when posted, meaning it joins the balance and starts
earning itself, which is what compounding actually is and is
modelled here as an explicit event rather than a formula, so the
ledger shows the moment it happened.
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
class Posting:
    through: datetime.date
    days: int
    interest: Money
    balance_after: Money


@dataclass
class InterestAccount:
    id: str
    balance: Money
    annual_rate: Fraction
    opened: datetime.date
    convention: DayCount = DayCount.ACT_365F
    posted_through: datetime.date | None = None
    movements: list[tuple[datetime.date, Money]] = field(default_factory=list)
    postings: list[Posting] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.annual_rate < 0:
            raise Refused("an interest rate on a deposit is not negative")
        if self.posted_through is None:
            self.posted_through = self.opened

    def deposit(self, amount: Money, on: datetime.date) -> Money:
        self._guard(amount)
        self.movements.append((on, amount))
        return self.balance_on(on)

    def withdraw(self, amount: Money, on: datetime.date) -> Money:
        self._guard(amount)
        if amount > self.balance_on(on):
            raise Refused(
                f"a withdrawal of {amount.format()} exceeds the "
                f"{self.balance_on(on).format()} in account {self.id!r}"
            )
        self.movements.append((on, -amount))
        return self.balance_on(on)

    def balance_on(self, as_of: datetime.date) -> Money:
        total = self.balance
        for date, amount in self.movements:
            if date <= as_of:
                total = total + amount
        return total

    def accrued_between(
        self, start: datetime.date, end: datetime.date
    ) -> Fraction:
        if end < start:
            raise Refused("an accrual period ends after it begins")
        total = Fraction(0)
        current = start
        while current < end:
            nxt = current + datetime.timedelta(days=1)
            balance = self.balance_on(current)
            if balance.is_positive():
                fraction = year_fraction(current, nxt, self.convention)
                total += Fraction(balance.units) * self.annual_rate * fraction
            current = nxt
        return total

    def accrued_since_posting(self, through: datetime.date) -> Fraction:
        return self.accrued_between(self.posted_through, through)

    def post_interest(self, through: datetime.date) -> Posting:
        if through < self.posted_through:
            raise Refused(
                f"account {self.id!r} is already posted through "
                f"{self.posted_through.isoformat()}; posting backward would pay "
                "for days already paid"
            )
        days = (through - self.posted_through).days
        exact = self.accrued_since_posting(through)
        interest = round_money(exact, self.balance.currency, Rounding.HALF_EVEN)
        if interest.is_positive():
            # Capitalizing: the interest joins the balance and starts earning.
            self.movements.append((through, interest))
        self.posted_through = through
        posting = Posting(
            through=through,
            days=days,
            interest=interest,
            balance_after=self.balance_on(through),
        )
        self.postings.append(posting)
        return posting

    def total_interest_posted(self) -> Money:
        total = Money.zero(self.balance.currency)
        for posting in self.postings:
            total = total + posting.interest
        return total

    def _guard(self, amount: Money) -> None:
        if amount.currency != self.balance.currency:
            raise Refused(
                f"account {self.id!r} holds {self.balance.currency}, not "
                f"{amount.currency}"
            )
        if not amount.is_positive():
            raise Refused("an account movement is a positive amount")
