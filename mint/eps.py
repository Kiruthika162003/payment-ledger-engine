"""Earnings per share: the weighted average denominator, and what dilution does to it.

Earnings per share looks like a division and is mostly a question
about the denominator. Shares issued halfway through the year did
not earn a full year's profit, so the denominator is the weighted
average number of shares outstanding, weighted by the fraction of
the period each tranche existed. Using the closing count instead
understates earnings per share in a year of issuance and overstates
it in a year of buybacks, which is precisely when management most
wants the number to look good. Diluted earnings per share then asks
what would happen if every instrument that could become a share
did: options, convertibles, and the rest. The rule that makes it
honest is that an instrument is only included if it is dilutive,
meaning it reduces earnings per share; an out-of-the-money option
would improve the figure and is excluded, because presenting the
best of the two would defeat the purpose of publishing the worse
one. This module computes both and reports which instruments were
excluded as antidilutive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class ShareTranche:
    shares: int
    fraction_of_period: Fraction

    def __post_init__(self) -> None:
        if self.shares == 0:
            raise Refused("a tranche changes the share count by a nonzero amount")
        if self.fraction_of_period <= 0 or self.fraction_of_period > 1:
            raise Refused(
                "a tranche exists for a fraction of the period above zero and "
                "at most one"
            )

    def weighted(self) -> Fraction:
        return self.shares * self.fraction_of_period


@dataclass(frozen=True)
class Convertible:
    name: str
    potential_shares: int
    earnings_added_back: Money

    def __post_init__(self) -> None:
        if self.potential_shares < 1:
            raise Refused(f"instrument {self.name!r} converts into at least one share")


@dataclass
class EarningsPerShare:
    net_income: Money
    tranches: list[ShareTranche] = field(default_factory=list)
    instruments: list[Convertible] = field(default_factory=list)

    def add_tranche(self, shares: int, fraction: Fraction) -> ShareTranche:
        tranche = ShareTranche(shares, fraction)
        self.tranches.append(tranche)
        return tranche

    def add_instrument(self, instrument: Convertible) -> Convertible:
        instrument.earnings_added_back.same_currency(self.net_income)
        self.instruments.append(instrument)
        return instrument

    def weighted_average_shares(self) -> Fraction:
        total = Fraction(0)
        for tranche in self.tranches:
            total += tranche.weighted()
        return total

    def basic(self) -> Fraction | None:
        shares = self.weighted_average_shares()
        if shares <= 0:
            return None
        return Fraction(self.net_income.units, 1) / shares

    def is_dilutive(self, instrument: Convertible) -> bool:
        base = self.basic()
        if base is None:
            return False
        shares = self.weighted_average_shares() + instrument.potential_shares
        earnings = self.net_income.units + instrument.earnings_added_back.units
        return Fraction(earnings, 1) / shares < base

    def dilutive_instruments(self) -> list[Convertible]:
        return [item for item in self.instruments if self.is_dilutive(item)]

    def antidilutive_instruments(self) -> list[Convertible]:
        # Excluded on purpose: including them would improve the figure, and
        # publishing the better of the two defeats the point of diluted EPS.
        return [item for item in self.instruments if not self.is_dilutive(item)]

    def diluted(self) -> Fraction | None:
        base = self.basic()
        if base is None:
            return None
        shares = self.weighted_average_shares()
        earnings = Fraction(self.net_income.units)
        for instrument in self.dilutive_instruments():
            shares += instrument.potential_shares
            earnings += instrument.earnings_added_back.units
        return earnings / shares

    def dilution_effect(self) -> Fraction | None:
        base = self.basic()
        diluted = self.diluted()
        if base is None or diluted is None:
            return None
        return base - diluted

    def is_diluted(self) -> bool:
        effect = self.dilution_effect()
        return effect is not None and effect > 0
