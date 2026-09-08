"""Recurring entries: a template plus a schedule, generated once per due date.

Rent, depreciation, and subscription revenue produce the same entry
every month, and the risk in automating them is not that an entry
is missed but that one is posted twice: a job that runs late, runs
again, and books February's rent a second time. This module makes
the generator idempotent by construction. A recurring template
knows its schedule and the dates it has already generated, so
asking it for the entries due through a date returns only the ones
not yet produced, and asking twice in a row returns nothing the
second time. The schedule advances by months from an anchor date
using the clamping rule, so a template anchored on the thirty-first
generates on the twenty-eighth in February and returns to the
thirty-first in March rather than drifting. A template can end after
a fixed count of occurrences or on a date, and one with neither runs
until told to stop, which is the honest default for something like
rent that has no scheduled end. The template holds the postings
rather than an entry, since the date differs each time and an entry
without its own date would be a half-built object waiting to be
misused.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.calendarutil import add_months
from mint.entry import Entry, entry
from mint.errors import Refused
from mint.posting import Posting


@dataclass
class RecurringTemplate:
    name: str
    postings: tuple[Posting, ...]
    anchor: datetime.date
    memo: str = ""
    occurrences: int | None = None
    until: datetime.date | None = None
    generated: list[datetime.date] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.postings:
            raise Refused(f"template {self.name!r} has no postings to repeat")
        if self.occurrences is not None and self.occurrences < 1:
            raise Refused("a recurring template runs at least once or not at all")

    def scheduled_dates(self, through: datetime.date) -> list[datetime.date]:
        dates: list[datetime.date] = []
        index = 0
        while True:
            if self.occurrences is not None and index >= self.occurrences:
                break
            due = add_months(self.anchor, index)
            if due > through:
                break
            if self.until is not None and due > self.until:
                break
            dates.append(due)
            index += 1
        return dates

    def pending(self, through: datetime.date) -> list[datetime.date]:
        already = set(self.generated)
        return [due for due in self.scheduled_dates(through) if due not in already]

    def generate(self, through: datetime.date) -> list[Entry]:
        produced: list[Entry] = []
        for due in self.pending(through):
            produced.append(
                entry(
                    list(self.postings),
                    due,
                    memo=self.memo or self.name,
                    ref=self.name,
                    tags=frozenset({"recurring"}),
                )
            )
            self.generated.append(due)
        return produced

    def is_finished(self, as_of: datetime.date) -> bool:
        if self.occurrences is not None:
            return len(self.generated) >= self.occurrences
        return self.until is not None and as_of > self.until
