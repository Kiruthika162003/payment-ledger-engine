"""Leases: recognizing the obligation up front and unwinding it as payments fall.

Modern lease accounting stopped letting an operating lease sit off
the balance sheet. A lessee now recognizes a liability for the
present value of the payments it has committed to, and a
right-of-use asset for the same amount, and then unwinds both: the
liability grows by interest and shrinks by each payment, while the
asset amortizes on a straight line over the term. The two do not
move in step, which is the point people miss, and the difference
between them is what makes early-year expense higher than a
straight rent charge. This module builds both schedules. The
liability schedule is the one that must close exactly on zero, so
the final period's principal reduction is whatever remains rather
than a formula result, the same discipline the loan schedule uses.
Payments in advance and in arrears are both supported, since real
leases pay rent at the start of the month and the choice shifts the
opening liability by one period's discounting, which is money, not
a detail.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.annuity import AnnuityTerms, present_value
from mint.errors import Refused
from mint.money import Money
from mint.rounding import round_money, split


@dataclass(frozen=True)
class LeaseRow:
    period: int
    opening: int
    interest: int
    payment: int
    closing: int
    amortization: int
    asset_closing: int


@dataclass(frozen=True)
class LeaseSchedule:
    initial_liability: Money
    rows: tuple[LeaseRow, ...]

    def total_interest(self) -> Money:
        return Money.from_minor(
            sum(row.interest for row in self.rows), self.initial_liability.currency
        )

    def total_payments(self) -> Money:
        return Money.from_minor(
            sum(row.payment for row in self.rows), self.initial_liability.currency
        )

    def final_liability(self) -> int:
        return self.rows[-1].closing if self.rows else self.initial_liability.units

    def final_asset(self) -> int:
        return self.rows[-1].asset_closing if self.rows else self.initial_liability.units

    def closes(self) -> bool:
        return self.final_liability() == 0 and self.final_asset() == 0


def initial_liability(
    payment: Money, rate: Fraction, periods: int, in_advance: bool = False
) -> Money:
    return present_value(AnnuityTerms(payment, rate, periods, due=in_advance))


def schedule(
    payment: Money, rate: Fraction, periods: int, in_advance: bool = False
) -> LeaseSchedule:
    if periods < 1:
        raise Refused("a lease runs for at least one period")
    if rate < 0:
        raise Refused("a lease discount rate is not negative")
    liability = initial_liability(payment, rate, periods, in_advance)
    currency = payment.currency
    amortization_shares = split(liability, periods)

    rows: list[LeaseRow] = []
    balance = liability.units
    asset = liability.units
    for period in range(1, periods + 1):
        if in_advance:
            reduction_before = min(payment.units, balance)
            balance -= reduction_before
            interest = round_money(Fraction(balance) * rate, currency).units
            balance += interest
            paid = reduction_before
        else:
            interest = round_money(Fraction(balance) * rate, currency).units
            balance += interest
            paid = min(payment.units, balance)
            balance -= paid
        if period == periods:
            # The last period retires whatever remains, so the schedule
            # closes on zero rather than a rounding residue.
            paid += balance
            balance = 0
        amortization = amortization_shares[period - 1].units
        asset -= amortization
        rows.append(
            LeaseRow(
                period=period,
                opening=liability.units if period == 1 else rows[-1].closing,
                interest=interest,
                payment=paid,
                closing=balance,
                amortization=amortization,
                asset_closing=asset,
            )
        )
    return LeaseSchedule(initial_liability=liability, rows=tuple(rows))
