"""Amortization: a level payment split into interest and principal, ending at zero.

A loan amortization schedule answers, for each payment, how much is
interest and how much pays down the balance, and its defining
requirement is that the balance ends at exactly zero, not a cent
above or below. The level payment is the constant amount whose
present value over the term equals the principal, computed here in
exact fractions and rounded once, but rounding the payment means
the arithmetic will not land perfectly on zero on its own, so this
module does what real lenders do: it holds the payment level for
every period but the last, and lets the final payment be whatever
retires the remaining balance, absorbing the accumulated rounding.
That is why a mortgage's last payment is often a few cents off the
others, and pretending otherwise is how a schedule leaves a
phantom balance the borrower is told they still owe. Interest each
period is computed on the outstanding balance, so early payments
are mostly interest and late ones mostly principal, the shape every
borrower recognizes. An interest-free loan is handled as its own
case, splitting the principal evenly with the cent conserved,
rather than forcing it through a formula that divides by zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money, split


@dataclass(frozen=True)
class AmortRow:
    period: int
    payment: int
    interest: int
    principal: int
    balance: int


@dataclass(frozen=True)
class AmortSchedule:
    principal: Money
    level_payment: Money
    rows: tuple[AmortRow, ...]

    def total_paid(self) -> Money:
        return Money.from_minor(sum(r.payment for r in self.rows), self.principal.currency)

    def total_interest(self) -> Money:
        return Money.from_minor(sum(r.interest for r in self.rows), self.principal.currency)

    def final_balance(self) -> int:
        return self.rows[-1].balance if self.rows else self.principal.units


def schedule(
    principal: Money, annual_rate: Fraction, periods: int, per_year: int
) -> AmortSchedule:
    if periods < 1:
        raise Refused("an amortization needs at least one payment")
    if per_year < 1:
        raise Refused("payments happen at least once a year")
    if annual_rate < 0:
        raise Refused("an amortization rate is not negative")
    currency = principal.currency
    rate = annual_rate / per_year

    if rate == 0:
        shares = split(principal, periods)
        rows = []
        balance = principal.units
        for index, share in enumerate(shares, start=1):
            balance -= share.units
            rows.append(AmortRow(index, share.units, 0, share.units, balance))
        return AmortSchedule(principal, shares[0], tuple(rows))

    level = _payment_for(principal.units, rate, periods, currency)
    rows = []
    balance = principal.units
    for period in range(1, periods + 1):
        interest = round_money(Fraction(balance) * rate, currency).units
        if period == periods:
            principal_paid = balance
            payment = interest + principal_paid
        else:
            principal_paid = min(level - interest, balance)
            payment = interest + principal_paid
        balance -= principal_paid
        rows.append(AmortRow(period, payment, interest, principal_paid, balance))
    return AmortSchedule(principal, Money.from_minor(level, currency), tuple(rows))


def _payment_for(principal_units: int, rate: Fraction, periods: int, currency: str) -> int:
    factor = (1 + rate) ** periods
    exact = Fraction(principal_units) * rate * factor / (factor - 1)
    return round_money(exact, currency, Rounding.HALF_EVEN).units
