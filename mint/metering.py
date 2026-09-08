"""Usage metering: counting what a customer consumed, by the rule their plan states.

Metered billing turns a stream of usage events into one number per
period, and the aggregation rule is part of the contract rather than
an implementation detail. Summing is the obvious one, appropriate
for consumption that accumulates like gigabytes transferred. Peak
is right for capacity, where a customer pays for the most they used
at once and the rest of the month is irrelevant. Unique counting
suits per-seat billing, where the same user active twenty times is
one seat. Last-value applies to a subscription quantity that
changes during the period. Each rule gives a different bill from
identical events, so this module names them and refuses to pick a
default, since silently summing peak-priced usage produces an
invoice thirty times too large. Events outside the billing period
are excluded rather than clamped, because usage in March is March's
regardless of when it arrived, and late-arriving events for a
closed period are reported separately so they can be billed in
arrears rather than silently dropped or silently added to a period
already invoiced.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.errors import Refused


class Aggregation(Enum):
    SUM = "sum"
    PEAK = "peak"
    UNIQUE = "unique"
    LAST = "last"


@dataclass(frozen=True)
class UsageEvent:
    at: datetime.datetime
    quantity: int
    subject: str = ""
    recorded_at: datetime.datetime | None = None

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise Refused("a usage quantity is not negative")

    def known_at(self) -> datetime.datetime:
        # When the meter learned of the usage, which is not when it happened;
        # the gap between the two is what makes an arrival late.
        return self.recorded_at or self.at


@dataclass
class Meter:
    name: str
    aggregation: Aggregation
    events: list[UsageEvent] = field(default_factory=list)

    def record(self, event: UsageEvent) -> UsageEvent:
        self.events.append(event)
        return event

    def in_period(
        self, start: datetime.datetime, end: datetime.datetime
    ) -> list[UsageEvent]:
        if end < start:
            raise Refused("a billing period ends after it begins")
        return [event for event in self.events if start <= event.at <= end]

    def late_arrivals(
        self,
        start: datetime.datetime,
        end: datetime.datetime,
        closed_at: datetime.datetime,
    ) -> list[UsageEvent]:
        # Events dated inside a period but learned of after it closed; they
        # belong in arrears rather than in a period already invoiced.
        return [
            event
            for event in self.in_period(start, end)
            if event.known_at() > closed_at
        ]

    def quantity_for(
        self, start: datetime.datetime, end: datetime.datetime
    ) -> int:
        window = self.in_period(start, end)
        if not window:
            return 0
        if self.aggregation is Aggregation.SUM:
            return sum(event.quantity for event in window)
        if self.aggregation is Aggregation.PEAK:
            return max(event.quantity for event in window)
        if self.aggregation is Aggregation.UNIQUE:
            return len({event.subject for event in window if event.subject})
        return sorted(window, key=lambda event: event.at)[-1].quantity

    def event_count(
        self, start: datetime.datetime, end: datetime.datetime
    ) -> int:
        return len(self.in_period(start, end))
