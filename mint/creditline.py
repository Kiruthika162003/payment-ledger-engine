"""Revolving credit: drawing, repaying, and paying interest only on what is drawn.

A revolving credit line is not a loan with a schedule; it is a
limit a borrower can draw against and repay repeatedly, and the
interest is charged on the balance actually outstanding day by day
rather than on the limit. Getting that right means accruing on the
drawn balance over the days it was drawn, which is why this module
tracks movements with their dates rather than a single balance:
borrowing on the twentieth and repaying on the twenty-second costs
two days of interest, and a system that accrues on the month-end
balance charges nothing at all for it. A commitment fee is charged
on the undrawn portion, which is how lenders price the option to
borrow, and it is the mirror of the interest: together they mean a
borrower pays something whether they draw or not. Drawing past the
limit is refused with the headroom named, and the limit can be
reduced below the drawn balance, which does not claw money back but
does block further draws, since that is what a lender actually does
when it loses confidence.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from fractions import Fraction

from mint.daycount import DayCount, year_fraction
from mint.errors import Refused
from mint.money import Money
from mint.rounding import round_money


@dataclass(frozen=True)
class Movement:
    date: datetime.date
    amount: Money
    kind: str


@dataclass
class CreditLine:
    id: str
    limit: Money
    annual_rate: Fraction
    commitment_rate: Fraction = Fraction(0)
    convention: DayCount = DayCount.ACT_365F
    movements: list[Movement] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.limit.is_positive():
            raise Refused("a credit line has a positive limit")
        if self.annual_rate < 0 or self.commitment_rate < 0:
            raise Refused("credit rates are not negative")

    def drawn(self, as_of: datetime.date) -> Money:
        total = Money.zero(self.limit.currency)
        for movement in self.movements:
            if movement.date > as_of:
                continue
            if movement.kind == "draw":
                total = total + movement.amount
            else:
                total = total - movement.amount
        return total

    def available(self, as_of: datetime.date) -> Money:
        headroom = self.limit - self.drawn(as_of)
        if headroom.is_negative():
            return Money.zero(self.limit.currency)
        return headroom

    def draw(self, amount: Money, on: datetime.date) -> Money:
        self._guard(amount)
        if amount > self.available(on):
            raise Refused(
                f"a draw of {amount.format()} exceeds the "
                f"{self.available(on).format()} of headroom on line {self.id!r}"
            )
        self.movements.append(Movement(on, amount, "draw"))
        return self.drawn(on)

    def repay(self, amount: Money, on: datetime.date) -> Money:
        self._guard(amount)
        if amount > self.drawn(on):
            raise Refused(
                f"a repayment of {amount.format()} exceeds the "
                f"{self.drawn(on).format()} outstanding on line {self.id!r}"
            )
        self.movements.append(Movement(on, amount, "repay"))
        return self.drawn(on)

    def reduce_limit(self, new_limit: Money, on: datetime.date) -> Money:
        self._guard(new_limit)
        if new_limit > self.limit:
            raise Refused("reducing a limit does not raise it")
        self.limit = new_limit
        # A limit below the drawn balance blocks new draws without clawing
        # back money already advanced.
        return self.available(on)

    def interest_for(
        self, start: datetime.date, end: datetime.date
    ) -> Money:
        if end < start:
            raise Refused("an interest period ends after it begins")
        total = Fraction(0)
        current = start
        while current < end:
            nxt = current + datetime.timedelta(days=1)
            balance = self.drawn(current)
            if balance.is_positive():
                fraction = year_fraction(current, nxt, self.convention)
                total += Fraction(balance.units) * self.annual_rate * fraction
            current = nxt
        return round_money(total, self.limit.currency)

    def commitment_fee_for(
        self, start: datetime.date, end: datetime.date
    ) -> Money:
        if self.commitment_rate == 0:
            return Money.zero(self.limit.currency)
        total = Fraction(0)
        current = start
        while current < end:
            nxt = current + datetime.timedelta(days=1)
            undrawn = self.available(current)
            if undrawn.is_positive():
                fraction = year_fraction(current, nxt, self.convention)
                total += Fraction(undrawn.units) * self.commitment_rate * fraction
            current = nxt
        return round_money(total, self.limit.currency)

    def _guard(self, amount: Money) -> None:
        if amount.currency != self.limit.currency:
            raise Refused(
                f"line {self.id!r} is in {self.limit.currency}, not {amount.currency}"
            )
        if not amount.is_positive():
            raise Refused("a credit movement is a positive amount")
