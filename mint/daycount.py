"""Day-count conventions: the several honest answers to how much of a year passed.

Interest is a rate per year applied to a fraction of a year, and
the surprise for newcomers is that the fraction is not one number
but a convention, chosen in the contract, and the conventions
disagree on purpose. Actual over 365 counts real days over a
fixed year and is the retail default. Actual over 360 counts real
days but pretends the year is 360 days long, which quietly charges
a few more days of interest and is the money-market habit. Thirty
over 360 pretends every month has thirty days, so a loan's monthly
interest is identical regardless of the calendar, which is exactly
what a level-payment mortgage needs. Actual over actual splits the
period at the year boundary and weighs each part by the true
length of its own year, leap years included, which is the most
faithful to the calendar and the most annoying to compute. This
module implements all four and returns an exact fraction rather
than a float, because the whole point of pinning the convention is
that two parties compute the same interest to the cent, and a
float would let them drift apart in the last place.
"""

from __future__ import annotations

import datetime
from enum import Enum
from fractions import Fraction

from mint.errors import Refused


class DayCount(Enum):
    ACT_365F = "act/365f"
    ACT_360 = "act/360"
    THIRTY_360 = "30/360"
    ACT_ACT = "act/act"


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _thirty_360_days(start: datetime.date, end: datetime.date) -> int:
    d1 = min(start.day, 30)
    d2 = end.day
    if d1 == 30 and d2 == 31:
        d2 = 30
    return 360 * (end.year - start.year) + 30 * (end.month - start.month) + (d2 - d1)


def _act_act(start: datetime.date, end: datetime.date) -> Fraction:
    if start.year == end.year:
        denom = 366 if _is_leap(start.year) else 365
        return Fraction((end - start).days, denom)
    total = Fraction(0)
    first_year_end = datetime.date(start.year + 1, 1, 1)
    total += Fraction((first_year_end - start).days, 366 if _is_leap(start.year) else 365)
    total += Fraction(end.year - start.year - 1)
    last_year_start = datetime.date(end.year, 1, 1)
    total += Fraction((end - last_year_start).days, 366 if _is_leap(end.year) else 365)
    return total


def year_fraction(
    start: datetime.date, end: datetime.date, convention: DayCount = DayCount.ACT_365F
) -> Fraction:
    if end < start:
        raise Refused(
            "the period ends before it begins; interest does not run backward"
        )
    if convention is DayCount.ACT_365F:
        return Fraction((end - start).days, 365)
    if convention is DayCount.ACT_360:
        return Fraction((end - start).days, 360)
    if convention is DayCount.THIRTY_360:
        return Fraction(_thirty_360_days(start, end), 360)
    return _act_act(start, end)
