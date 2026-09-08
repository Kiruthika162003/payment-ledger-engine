"""Velocity limits: how much and how often, counted over a sliding window.

Velocity checks are the cheapest fraud control that works: a card
that has been used four times in a minute or has spent ten thousand
dollars in an hour is behaving unlike its owner, whatever the
individual amounts look like. The control is only as good as its
window, and the window is where implementations go wrong. A fixed
calendar window resets on the hour, so an attacker who spends the
limit at 10:59 and again at 11:01 passes twice within two minutes;
a sliding window counts backward from now and closes that seam.
This module uses the sliding window and counts both the number of
attempts and their total value, since the two limits catch
different attacks: many small charges testing a stolen card, and
one large charge draining it. A rejected attempt still counts
toward the velocity, because an attacker probing limits should not
get free attempts by being declined, and this is the detail that a
naive implementation, recording only successes, leaves open.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class Attempt:
    at: datetime.datetime
    amount: Money
    accepted: bool


@dataclass
class VelocityLimit:
    window: datetime.timedelta
    max_count: int | None = None
    max_amount: Money | None = None

    def __post_init__(self) -> None:
        if self.window <= datetime.timedelta(0):
            raise Refused("a velocity window spans a positive amount of time")
        if self.max_count is None and self.max_amount is None:
            raise Refused(
                "a velocity limit caps a count, an amount, or both; one that "
                "caps neither permits everything"
            )
        if self.max_count is not None and self.max_count < 1:
            raise Refused("a velocity count limit allows at least one attempt")


@dataclass
class VelocityCounter:
    currency: str
    limits: list[VelocityLimit] = field(default_factory=list)
    attempts: list[Attempt] = field(default_factory=list)

    def in_window(
        self, now: datetime.datetime, window: datetime.timedelta
    ) -> list[Attempt]:
        cutoff = now - window
        return [item for item in self.attempts if item.at > cutoff]

    def count_in(self, now: datetime.datetime, window: datetime.timedelta) -> int:
        return len(self.in_window(now, window))

    def amount_in(
        self, now: datetime.datetime, window: datetime.timedelta
    ) -> Money:
        total = Money.zero(self.currency)
        for item in self.in_window(now, window):
            total = total + item.amount
        return total

    def would_breach(self, amount: Money, now: datetime.datetime) -> str | None:
        if amount.currency != self.currency:
            raise Refused(
                f"this counter tracks {self.currency}, not {amount.currency}"
            )
        for limit in self.limits:
            over_count = (
                limit.max_count is not None
                and self.count_in(now, limit.window) + 1 > limit.max_count
            )
            if over_count:
                return (
                    f"more than {limit.max_count} attempts in "
                    f"{limit.window}; the account is moving unlike its owner"
                )
            if limit.max_amount is not None:
                projected = self.amount_in(now, limit.window) + amount
                if projected > limit.max_amount:
                    return (
                        f"more than {limit.max_amount.format()} in "
                        f"{limit.window}"
                    )
        return None

    def record(self, amount: Money, now: datetime.datetime, accepted: bool) -> Attempt:
        # A declined attempt still counts, or probing the limit is free.
        attempt = Attempt(now, amount, accepted)
        self.attempts.append(attempt)
        return attempt

    def check_and_record(self, amount: Money, now: datetime.datetime) -> str | None:
        breach = self.would_breach(amount, now)
        self.record(amount, now, accepted=breach is None)
        return breach

    def accepted_count(self) -> int:
        return sum(1 for item in self.attempts if item.accepted)
