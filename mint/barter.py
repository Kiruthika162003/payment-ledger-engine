"""Barter: an exchange with no cash, measured at fair value if anything really changed.

Two businesses swapping services have made a real transaction even
though no money moved, and it is recorded at the fair value of what
was given up or received, whichever is more reliably measurable.
The reason the rule matters is the abuse it prevents: two companies
can swap equivalent services at an inflated notional value and both
book large revenues without either being better off, which is
exactly what a wave of internet companies did with advertising
swaps. The guard is commercial substance. If the exchange does not
change the amount, timing, or risk of either party's future cash
flows, nothing has really happened and no gain may be recognized;
the asset received simply carries the book value of the asset given
up. This module applies that test, refuses a gain on an exchange
that lacks substance, and refuses a valuation neither side can
measure reliably, because a barter valued at whatever the parties
say is a number with nothing behind it.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum

from mint.errors import Refused
from mint.money import Money


class Measurability(Enum):
    GIVEN_MORE_RELIABLE = "given_more_reliable"
    RECEIVED_MORE_RELIABLE = "received_more_reliable"
    NEITHER_RELIABLE = "neither_reliable"


@dataclass(frozen=True)
class ExchangeResult:
    recorded_value: Money
    gain: Money
    basis: str
    has_substance: bool

    def is_gain(self) -> bool:
        return self.gain.is_positive()

    def reconciles(self, book_value: Money) -> bool:
        return self.recorded_value - book_value == self.gain


@dataclass
class BarterExchange:
    id: str
    date: datetime.date
    book_value_given: Money
    fair_value_given: Money | None = None
    fair_value_received: Money | None = None
    measurability: Measurability = Measurability.GIVEN_MORE_RELIABLE
    changes_cash_flows: bool = True

    def __post_init__(self) -> None:
        if self.book_value_given.is_negative():
            raise Refused("a book value is not negative")
        for value in (self.fair_value_given, self.fair_value_received):
            if value is not None:
                value.same_currency(self.book_value_given)
                if value.is_negative():
                    raise Refused("a fair value is not negative")

    def has_commercial_substance(self) -> bool:
        # If nothing about future cash flows changed, nothing really happened.
        return self.changes_cash_flows

    def measured_fair_value(self) -> Money:
        if self.measurability is Measurability.NEITHER_RELIABLE:
            raise Refused(
                f"exchange {self.id!r} has no reliably measurable side; a barter "
                "valued at whatever the parties say is a number with nothing "
                "behind it"
            )
        if self.measurability is Measurability.GIVEN_MORE_RELIABLE:
            if self.fair_value_given is None:
                raise Refused(
                    f"exchange {self.id!r} claims the given side is measurable "
                    "but supplies no fair value for it"
                )
            return self.fair_value_given
        if self.fair_value_received is None:
            raise Refused(
                f"exchange {self.id!r} claims the received side is measurable "
                "but supplies no fair value for it"
            )
        return self.fair_value_received

    def record(self) -> ExchangeResult:
        if not self.has_commercial_substance():
            # Carried over at book value, so no gain appears from a swap that
            # left both parties exactly where they were.
            return ExchangeResult(
                recorded_value=self.book_value_given,
                gain=Money.zero(self.book_value_given.currency),
                basis="carried over at book value, the exchange lacking substance",
                has_substance=False,
            )
        fair_value = self.measured_fair_value()
        side = (
            "the fair value of what was given up"
            if self.measurability is Measurability.GIVEN_MORE_RELIABLE
            else "the fair value of what was received"
        )
        return ExchangeResult(
            recorded_value=fair_value,
            gain=fair_value - self.book_value_given,
            basis=side,
            has_substance=True,
        )

    def gain_if_recognized(self) -> Money:
        return self.record().gain

    def would_inflate_revenue(self, notional: Money) -> bool:
        # The advertising-swap pattern: a large notional on an exchange with
        # no substance behind it.
        notional.same_currency(self.book_value_given)
        return not self.has_commercial_substance() and notional > self.book_value_given
