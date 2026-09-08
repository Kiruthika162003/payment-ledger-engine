"""Interest: simple and compound, computed exactly and rounded once at the end.

Interest is where small rounding sins compound into real money, so
this module keeps the whole calculation in exact fractions and
rounds a single time when it hands back money. Simple interest is
principal times rate times the year fraction from the chosen
day-count convention, which is the honest way to say it depends on
how the contract counts days rather than assuming a calendar.
Compound interest raises one plus the periodic rate to the number
of periods, exactly, because the periodic rate is a fraction and a
fraction to an integer power stays a fraction, so a year of daily
compounding does not accumulate the floating-point drift that makes
two systems disagree on a statement. The effective annual rate is
offered as its own figure, since a nominal rate compounded monthly
is not the rate a borrower actually pays and quoting the nominal as
if it were the effective is the oldest trick in lending. Every
entry point rounds only at the boundary and every rate is a
fraction, so the interest this module computes is the interest a
careful auditor recomputes by hand and finds identical.
"""

from __future__ import annotations

import datetime
from fractions import Fraction

from mint.daycount import DayCount, year_fraction
from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


def simple_interest(
    principal: Money,
    annual_rate: Fraction,
    start: datetime.date,
    end: datetime.date,
    convention: DayCount = DayCount.ACT_365F,
    mode: Rounding = Rounding.HALF_EVEN,
) -> Money:
    if annual_rate < 0:
        raise Refused("a negative interest rate is a fee in disguise; state it as one")
    fraction = year_fraction(start, end, convention)
    exact = principal.times(annual_rate * fraction)
    return round_money(exact, principal.currency, mode)


def compound_factor(periodic_rate: Fraction, periods: int) -> Fraction:
    if periods < 0:
        raise Refused("a compounding cannot run a negative number of periods")
    return (1 + periodic_rate) ** periods


def compound_interest(
    principal: Money,
    annual_rate: Fraction,
    periods: int,
    per_year: int,
    mode: Rounding = Rounding.HALF_EVEN,
) -> Money:
    if per_year < 1:
        raise Refused("a compounding happens at least once a year")
    if annual_rate < 0:
        raise Refused("a negative interest rate is a fee in disguise; state it as one")
    factor = compound_factor(annual_rate / per_year, periods)
    grown = principal.times(factor)
    interest = grown - Fraction(principal.units)
    return round_money(interest, principal.currency, mode)


def effective_annual_rate(nominal: Fraction, per_year: int) -> Fraction:
    if per_year < 1:
        raise Refused("a rate compounds at least once a year")
    return (1 + nominal / per_year) ** per_year - 1


def future_value(
    principal: Money,
    annual_rate: Fraction,
    periods: int,
    per_year: int,
    mode: Rounding = Rounding.HALF_EVEN,
) -> Money:
    factor = compound_factor(annual_rate / per_year, periods)
    return round_money(principal.times(factor), principal.currency, mode)
