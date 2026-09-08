"""Deferred revenue: cash taken up front, recognized as it is earned.

Money collected before the work is done is not revenue, it is a
liability: the business owes a year of service, and recognizing the
whole payment on day one overstates the period's profit and hides
the obligation. Deferred revenue is the discipline of holding that
cash as a liability and releasing it to revenue ratably as the
service is delivered. This module builds the release schedule. The
total is split across the periods with the cent conserved, so the
sum of what is recognized equals exactly what was collected and no
stub of a liability is left behind at the end, which is the failure
mode of a naive schedule that divides and rounds each period
independently. The schedule reports, for each period, the amount
recognized, the running total recognized, and the liability still
deferred, because those are the three figures a close needs: one
for the income statement, one for the tie-out, and one for the
balance sheet. Asking what has been recognized as of a date folds
the schedule rather than storing a second number, so the answer can
never drift from the schedule that produced it.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from mint.calendarutil import add_months
from mint.errors import Refused
from mint.money import Money
from mint.rounding import split


@dataclass(frozen=True)
class RecognitionRow:
    period: int
    date: datetime.date
    recognized: int
    cumulative: int
    deferred: int


@dataclass(frozen=True)
class DeferralSchedule:
    total: Money
    rows: tuple[RecognitionRow, ...]

    def recognized_through(self, as_of: datetime.date) -> Money:
        total = 0
        for row in self.rows:
            if row.date <= as_of:
                total = row.cumulative
        return Money.from_minor(total, self.total.currency)

    def deferred_at(self, as_of: datetime.date) -> Money:
        return self.total - self.recognized_through(as_of)

    def fully_recognized(self) -> bool:
        return bool(self.rows) and self.rows[-1].deferred == 0


def monthly_schedule(
    total: Money, start: datetime.date, months: int
) -> DeferralSchedule:
    if months < 1:
        raise Refused("a deferral runs over at least one period")
    if not total.is_positive():
        raise Refused("there is nothing to defer")
    shares = split(total, months)
    rows = []
    cumulative = 0
    for index, share in enumerate(shares):
        cumulative += share.units
        rows.append(
            RecognitionRow(
                period=index + 1,
                date=add_months(start, index),
                recognized=share.units,
                cumulative=cumulative,
                deferred=total.units - cumulative,
            )
        )
    return DeferralSchedule(total=total, rows=tuple(rows))
