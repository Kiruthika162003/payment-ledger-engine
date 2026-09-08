"""Calendar arithmetic: adding months honestly, and counting business days.

Adding a month to a date is not addition, it is a convention, and
the convention has to be stated because the naive answer does not
exist: there is no thirty-first of February, so a subscription
billed on the thirty-first of January bills again on the twenty-
eighth, and the following month on the thirty-first again if the
original day is remembered rather than the clamped one. This module
clamps to the last valid day of the target month and always
measures from the original date, so a run of monthly additions does
not walk backward through the calendar the way repeated one-month
steps from the clamped result would, drifting a January
thirty-first billing date permanently to the twenty-eighth. Business
days are the other calendar fiction a ledger needs: settlement,
value dates, and payment terms are counted in days the banks are
open, so the module skips weekends and a supplied holiday set, and
counts forward from the day after the start rather than including
it, which is the convention that makes two business days after
Friday land on Tuesday.
"""

from __future__ import annotations

import calendar
import datetime

from mint.errors import Refused


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def end_of_month(date: datetime.date) -> datetime.date:
    return datetime.date(date.year, date.month, days_in_month(date.year, date.month))


def add_months(date: datetime.date, months: int) -> datetime.date:
    total = date.month - 1 + months
    year = date.year + total // 12
    month = total % 12 + 1
    day = min(date.day, days_in_month(year, month))
    return datetime.date(year, month, day)


def month_series(start: datetime.date, count: int) -> list[datetime.date]:
    # Every step measures from the original date, so a January 31 start
    # returns to 31 in March rather than sticking at the clamped 28.
    if count < 1:
        raise Refused("a month series needs at least one date")
    return [add_months(start, offset) for offset in range(count)]


def is_weekend(date: datetime.date) -> bool:
    return date.weekday() >= 5


def is_business_day(
    date: datetime.date, holidays: frozenset[datetime.date] = frozenset()
) -> bool:
    return not is_weekend(date) and date not in holidays


def add_business_days(
    date: datetime.date, days: int, holidays: frozenset[datetime.date] = frozenset()
) -> datetime.date:
    if days < 0:
        raise Refused("counting business days backward needs its own verb")
    current = date
    remaining = days
    while remaining > 0:
        current += datetime.timedelta(days=1)
        if is_business_day(current, holidays):
            remaining -= 1
    return current


def business_days_between(
    start: datetime.date, end: datetime.date, holidays: frozenset[datetime.date] = frozenset()
) -> int:
    if end < start:
        raise Refused("the period ends before it begins")
    count = 0
    current = start + datetime.timedelta(days=1)
    while current <= end:
        if is_business_day(current, holidays):
            count += 1
        current += datetime.timedelta(days=1)
    return count
