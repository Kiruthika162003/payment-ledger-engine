"""Forward contracts: fixing tomorrow's rate today, and what that certainty costs.

A business owing a foreign supplier in three months can wait and
take whatever rate arrives, or buy the currency forward at a rate
agreed now. The forward rate is not a prediction; it is arithmetic.
It is the spot rate adjusted for the difference in interest rates
between the two currencies, because anything else would let someone
borrow in one currency, convert, lend in the other, and lock in a
profit with no risk. This module computes the forward rate from
that relationship, called covered interest parity, so the number it
produces is the one the market must quote rather than a guess about
where rates are going. Contracts are marked to market against the
prevailing rate so the gain or loss on the hedge is visible before
settlement, which is what makes hedging accounting honest: a
forward that has moved against you is a real loss whether or not it
has settled, and reporting only the settled ones hides the position
until it is too late to do anything about it.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from fractions import Fraction

from mint.conversion import convert_at
from mint.daycount import DayCount, year_fraction
from mint.errors import Refused
from mint.money import Money


def forward_rate(
    spot: Fraction,
    base_rate: Fraction,
    quote_rate: Fraction,
    start: datetime.date,
    maturity: datetime.date,
    convention: DayCount = DayCount.ACT_360,
) -> Fraction:
    if spot <= 0:
        raise Refused("a spot rate is a positive ratio")
    if base_rate < -1 or quote_rate < -1:
        raise Refused("an interest rate below minus one has no meaning here")
    fraction = year_fraction(start, maturity, convention)
    # Covered interest parity: any other rate would be a free profit.
    return spot * (1 + quote_rate * fraction) / (1 + base_rate * fraction)


@dataclass(frozen=True)
class ForwardContract:
    id: str
    notional: Money
    quote_currency: str
    agreed_rate: Fraction
    trade_date: datetime.date
    maturity: datetime.date

    def __post_init__(self) -> None:
        if self.maturity <= self.trade_date:
            raise Refused("a forward matures after it is traded")
        if self.agreed_rate <= 0:
            raise Refused("an agreed forward rate is positive")
        if not self.notional.is_positive():
            raise Refused("a forward has a positive notional")
        if self.notional.currency == self.quote_currency.upper():
            raise Refused("a forward exchanges two different currencies")

    def contracted_proceeds(self) -> Money:
        return convert_at(self.notional, self.quote_currency, self.agreed_rate)

    def market_proceeds(self, market_rate: Fraction) -> Money:
        if market_rate <= 0:
            raise Refused("a market rate is a positive ratio")
        return convert_at(self.notional, self.quote_currency, market_rate)

    def mark_to_market(self, market_rate: Fraction) -> Money:
        # Positive when the contract is worth more than the market, which is
        # a gain for the party that fixed the rate.
        return self.contracted_proceeds() - self.market_proceeds(market_rate)

    def is_in_the_money(self, market_rate: Fraction) -> bool:
        return self.mark_to_market(market_rate).is_positive()

    def days_to_maturity(self, as_of: datetime.date) -> int:
        return max(0, (self.maturity - as_of).days)

    def has_matured(self, as_of: datetime.date) -> bool:
        return as_of >= self.maturity

    def settle(self, market_rate: Fraction, as_of: datetime.date) -> Money:
        if not self.has_matured(as_of):
            raise Refused(
                f"forward {self.id!r} matures on {self.maturity.isoformat()} and "
                "cannot settle before then"
            )
        return self.mark_to_market(market_rate)


def hedge_ratio(exposure: Money, hedged: Money) -> Fraction | None:
    if exposure.units == 0:
        return None
    hedged.same_currency(exposure)
    return Fraction(hedged.units, exposure.units)


def is_over_hedged(exposure: Money, hedged: Money) -> bool:
    ratio = hedge_ratio(exposure, hedged)
    return ratio is not None and ratio > 1
