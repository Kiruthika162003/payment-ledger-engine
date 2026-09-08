"""Payout scheduling: which banking day the money actually lands on.

A processor promising daily payouts does not pay on Sunday, and a
merchant told to expect funds on a Saturday who receives them on
Tuesday concludes something went wrong. Payout dates are therefore
computed against banking days rather than calendar days, with a
delay measured in banking days too, so a Friday sale on a
two-day delay lands on Tuesday and not on Sunday. This module
handles the schedules processors actually offer: daily, weekly on a
chosen weekday, and monthly on a chosen day of the month with the
end-of-month clamp that stops a payout scheduled for the
thirty-first vanishing in February. Holidays are supplied rather
than assumed, since they differ by country and a hardcoded list is
wrong somewhere immediately. The module also answers the question a
merchant support agent is asked most: given that a sale happened on
this date, when does the money arrive, which is the composition of
the delay and the schedule rather than either alone.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum

from mint.calendarutil import add_business_days, add_months, days_in_month, is_business_day
from mint.errors import Refused


class Cadence(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass(frozen=True)
class PayoutSchedule:
    cadence: Cadence
    delay_days: int = 2
    weekday: int = 4
    day_of_month: int = 1
    holidays: frozenset[datetime.date] = frozenset()

    def __post_init__(self) -> None:
        if self.delay_days < 0:
            raise Refused("a settlement delay is not negative")
        if not 0 <= self.weekday <= 6:
            raise Refused("a weekday runs from zero for Monday to six for Sunday")
        if not 1 <= self.day_of_month <= 31:
            raise Refused("a day of the month runs from one to thirty-one")

    def next_banking_day(self, date: datetime.date) -> datetime.date:
        current = date
        while not is_business_day(current, self.holidays):
            current += datetime.timedelta(days=1)
        return current

    def _next_weekly(self, after: datetime.date) -> datetime.date:
        ahead = (self.weekday - after.weekday()) % 7
        if ahead == 0:
            ahead = 7
        return self.next_banking_day(after + datetime.timedelta(days=ahead))

    def _next_monthly(self, after: datetime.date) -> datetime.date:
        # Clamped, so a payout set for the thirty-first does not vanish in
        # February; it lands on the last day instead.
        candidate_month = after
        for _ in range(3):
            days = days_in_month(candidate_month.year, candidate_month.month)
            day = min(self.day_of_month, days)
            candidate = datetime.date(candidate_month.year, candidate_month.month, day)
            if candidate > after:
                return self.next_banking_day(candidate)
            candidate_month = add_months(candidate_month, 1)
        raise Refused("no monthly payout date could be found")

    def next_payout_after(self, date: datetime.date) -> datetime.date:
        if self.cadence is Cadence.DAILY:
            return self.next_banking_day(date + datetime.timedelta(days=1))
        if self.cadence is Cadence.WEEKLY:
            return self._next_weekly(date)
        return self._next_monthly(date)

    def funds_available_on(self, sale_date: datetime.date) -> datetime.date:
        # The delay is counted in banking days, not calendar days.
        return add_business_days(sale_date, self.delay_days, self.holidays)

    def payout_for_sale(self, sale_date: datetime.date) -> datetime.date:
        available = self.funds_available_on(sale_date)
        if self.cadence is Cadence.DAILY:
            return self.next_banking_day(available)
        return self.next_payout_after(available - datetime.timedelta(days=1))

    def days_to_money(self, sale_date: datetime.date) -> int:
        return (self.payout_for_sale(sale_date) - sale_date).days

    def upcoming(self, after: datetime.date, count: int) -> list[datetime.date]:
        if count < 1:
            raise Refused("a schedule preview covers at least one payout")
        dates: list[datetime.date] = []
        cursor = after
        for _ in range(count):
            cursor = self.next_payout_after(cursor)
            dates.append(cursor)
        return dates
