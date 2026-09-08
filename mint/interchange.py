"""Interchange: the part of a card fee that is not the processor's to keep.

The fee a merchant pays on a card transaction is mostly not the
processor's margin; it is interchange, set by the card networks and
passed to the issuing bank, plus a network assessment, plus
whatever the processor adds. Merchants who do not know this
negotiate the wrong number. The interchange rate itself depends on
several attributes of the transaction rather than one: the card
type, since a rewards card costs more than a plain one because
somebody funds the rewards; whether the card was present, since a
keyed transaction carries more fraud risk; and whether the card was
issued in the same region. This module holds those rates as a
lookup over those attributes and computes the three layers
separately, so a merchant statement can show what was interchange,
what was assessment, and what the processor actually kept. That
last figure is the only one negotiable, which is why separating it
is worth the trouble.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


class CardType(Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    REWARDS = "rewards"
    CORPORATE = "corporate"


class Presence(Enum):
    CARD_PRESENT = "card_present"
    CARD_NOT_PRESENT = "card_not_present"


@dataclass(frozen=True)
class RateKey:
    card_type: CardType
    presence: Presence
    cross_border: bool


@dataclass(frozen=True)
class Rate:
    percent: Fraction
    fixed: Money

    def __post_init__(self) -> None:
        if self.percent < 0 or self.percent >= 1:
            raise Refused("an interchange rate is a fraction below one")
        if self.fixed.is_negative():
            raise Refused("a fixed interchange component is not negative")

    def on(self, amount: Money) -> Money:
        return scale(amount, self.percent, Rounding.HALF_EVEN) + self.fixed


@dataclass(frozen=True)
class FeeBreakdown:
    amount: Money
    interchange: Money
    assessment: Money
    processor_margin: Money

    def total_fee(self) -> Money:
        return self.interchange + self.assessment + self.processor_margin

    def net_to_merchant(self) -> Money:
        return self.amount - self.total_fee()

    def negotiable_share(self) -> Fraction | None:
        if self.total_fee().units == 0:
            return None
        # Only the processor's own margin can be argued about.
        return Fraction(self.processor_margin.units, self.total_fee().units)

    def reconciles(self) -> bool:
        return self.net_to_merchant() + self.total_fee() == self.amount


@dataclass
class InterchangeTable:
    currency: str
    assessment_rate: Fraction
    processor_percent: Fraction
    processor_fixed: Money
    rates: dict[RateKey, Rate] = field(default_factory=dict)

    def set_rate(self, key: RateKey, rate: Rate) -> Rate:
        if rate.fixed.currency != self.currency:
            raise Refused(
                f"a rate in {rate.fixed.currency} does not belong to a "
                f"{self.currency} table"
            )
        self.rates[key] = rate
        return rate

    def rate_for(self, key: RateKey) -> Rate:
        if key not in self.rates:
            raise Refused(
                f"no interchange rate is held for {key.card_type.value}, "
                f"{key.presence.value}, cross-border {key.cross_border}; "
                "guessing one would misstate the merchant's cost"
            )
        return self.rates[key]

    def breakdown(self, amount: Money, key: RateKey) -> FeeBreakdown:
        if amount.currency != self.currency:
            raise Refused(
                f"this table prices {self.currency}, not {amount.currency}"
            )
        if not amount.is_positive():
            raise Refused("a card transaction is for a positive amount")
        interchange = self.rate_for(key).on(amount)
        assessment = scale(amount, self.assessment_rate, Rounding.HALF_EVEN)
        margin = (
            scale(amount, self.processor_percent, Rounding.HALF_EVEN)
            + self.processor_fixed
        )
        return FeeBreakdown(
            amount=amount,
            interchange=interchange,
            assessment=assessment,
            processor_margin=margin,
        )


def standard_table(currency: str = "USD") -> InterchangeTable:
    table = InterchangeTable(
        currency=currency,
        assessment_rate=Fraction(13, 10000),
        processor_percent=Fraction(3, 1000),
        processor_fixed=Money.of("0.10", currency),
    )
    fixed = Money.of("0.10", currency)
    table.set_rate(
        RateKey(CardType.DEBIT, Presence.CARD_PRESENT, False),
        Rate(Fraction(5, 1000), fixed),
    )
    table.set_rate(
        RateKey(CardType.CREDIT, Presence.CARD_PRESENT, False),
        Rate(Fraction(15, 1000), fixed),
    )
    table.set_rate(
        RateKey(CardType.CREDIT, Presence.CARD_NOT_PRESENT, False),
        Rate(Fraction(19, 1000), fixed),
    )
    table.set_rate(
        RateKey(CardType.REWARDS, Presence.CARD_NOT_PRESENT, False),
        Rate(Fraction(23, 1000), fixed),
    )
    table.set_rate(
        RateKey(CardType.REWARDS, Presence.CARD_NOT_PRESENT, True),
        Rate(Fraction(29, 1000), fixed),
    )
    return table
