"""Accounting periods: the calendar of months, and the door that closes on one.

A closed period is the promise that the numbers already reported
will not change underneath the people who read them. Once a month
is closed and its statements are issued, a late entry backdated
into it would silently restate a published figure, so the ledger
needs a control that refuses the posting and points the poster at
the open period instead. This module holds the calendar of periods
and their states. An open period accepts postings. A closed period
refuses them but can be reopened by someone who accepts that
restating is what they are doing. A locked period cannot even be
reopened, which is the state a period reaches once its numbers have
gone to a tax authority and are no longer the company's to revise.
Periods must tile the calendar without gaps or overlaps, because a
date that falls in no period has no rule governing it and a date in
two periods has contradictory ones, so the calendar refuses a
period that overlaps one it already holds and reports any gap it
notices rather than quietly letting a day fall through.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.calendarutil import add_months, end_of_month
from mint.errors import Refused


class PeriodStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    LOCKED = "locked"


@dataclass
class AccountingPeriod:
    name: str
    start: datetime.date
    end: datetime.date
    status: PeriodStatus = PeriodStatus.OPEN

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise Refused(f"period {self.name!r} ends before it begins")

    def contains(self, date: datetime.date) -> bool:
        return self.start <= date <= self.end

    def accepts_postings(self) -> bool:
        return self.status is PeriodStatus.OPEN

    def overlaps(self, other: AccountingPeriod) -> bool:
        return self.start <= other.end and other.start <= self.end


@dataclass
class PeriodCalendar:
    periods: list[AccountingPeriod] = field(default_factory=list)

    def add(self, period: AccountingPeriod) -> AccountingPeriod:
        for existing in self.periods:
            if existing.overlaps(period):
                raise Refused(
                    f"period {period.name!r} overlaps {existing.name!r}; a date "
                    "in two periods has contradictory rules"
                )
        self.periods.append(period)
        self.periods.sort(key=lambda p: p.start)
        return period

    def add_months_from(self, start: datetime.date, count: int, prefix: str = "") -> None:
        for offset in range(count):
            first = add_months(start, offset)
            label = f"{prefix}{first.year}-{first.month:02d}"
            self.add(AccountingPeriod(label, first, end_of_month(first)))

    def period_for(self, date: datetime.date) -> AccountingPeriod:
        for period in self.periods:
            if period.contains(date):
                return period
        raise Refused(
            f"no accounting period covers {date.isoformat()}; a date governed "
            "by no period has no rule to follow"
        )

    def guard_posting(self, date: datetime.date) -> AccountingPeriod:
        period = self.period_for(date)
        if not period.accepts_postings():
            raise Refused(
                f"period {period.name!r} is {period.status.value}; a backdated "
                "entry would restate figures that have already been reported"
            )
        return period

    def close(self, name: str) -> AccountingPeriod:
        period = self.by_name(name)
        if period.status is PeriodStatus.LOCKED:
            raise Refused(f"period {name!r} is locked and cannot change state")
        period.status = PeriodStatus.CLOSED
        return period

    def reopen(self, name: str) -> AccountingPeriod:
        period = self.by_name(name)
        if period.status is PeriodStatus.LOCKED:
            raise Refused(
                f"period {name!r} is locked; its numbers have left the company "
                "and are no longer ours to revise"
            )
        period.status = PeriodStatus.OPEN
        return period

    def lock(self, name: str) -> AccountingPeriod:
        period = self.by_name(name)
        period.status = PeriodStatus.LOCKED
        return period

    def by_name(self, name: str) -> AccountingPeriod:
        for period in self.periods:
            if period.name == name:
                return period
        raise Refused(f"there is no period named {name!r}")

    def gaps(self) -> list[tuple[datetime.date, datetime.date]]:
        found: list[tuple[datetime.date, datetime.date]] = []
        for earlier, later in zip(self.periods, self.periods[1:], strict=False):
            expected = earlier.end + datetime.timedelta(days=1)
            if later.start > expected:
                found.append((expected, later.start - datetime.timedelta(days=1)))
        return found
