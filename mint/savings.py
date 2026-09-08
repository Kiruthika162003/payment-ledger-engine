"""Tiered savings rates: which rate applies to which slice of the balance.

Savings products advertise a rate and then qualify it, and the
qualification is the same distinction that trips people on income
tax: does the higher rate apply to the whole balance or only to the
part above the threshold. Both products exist. A banded account
pays each tier's rate on the slice inside that tier, so a balance
just over a threshold earns barely more than one just under. A
whole-balance account pays the reached tier's rate on everything,
which produces a jump at the threshold and an incentive to top up.
Advertising one and computing the other is a consumer complaint
waiting to happen, so this module names them and implements both.
The blended rate is reported alongside the interest, because that
is the number a saver can actually compare between products, and
for a banded account it is always below the headline rate, which is
exactly the fact the headline is designed to obscure.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


class TierStyle(Enum):
    BANDED = "banded"
    WHOLE_BALANCE = "whole_balance"


@dataclass(frozen=True)
class RateTier:
    floor: Money
    rate: Fraction

    def __post_init__(self) -> None:
        if self.rate < 0:
            raise Refused("a savings rate is not negative")
        if self.floor.is_negative():
            raise Refused("a tier floor is not negative")


@dataclass(frozen=True)
class SavingsProduct:
    name: str
    tiers: tuple[RateTier, ...]
    style: TierStyle

    def __post_init__(self) -> None:
        if not self.tiers:
            raise Refused("a savings product needs at least one tier")
        if self.tiers[0].floor.units != 0:
            raise Refused("the first tier starts at a zero balance")
        floors = [tier.floor.units for tier in self.tiers]
        if floors != sorted(floors) or len(set(floors)) != len(floors):
            raise Refused("tier floors must strictly increase")

    def currency(self) -> str:
        return self.tiers[0].floor.currency

    def headline_rate(self) -> Fraction:
        return max(tier.rate for tier in self.tiers)

    def reached_rate(self, balance: Money) -> Fraction:
        rate = self.tiers[0].rate
        for tier in self.tiers:
            if balance.units >= tier.floor.units:
                rate = tier.rate
        return rate

    def annual_interest(
        self, balance: Money, mode: Rounding = Rounding.HALF_EVEN
    ) -> Money:
        if balance.currency != self.currency():
            raise Refused(
                f"this product is in {self.currency()}, not {balance.currency}"
            )
        if balance.is_negative():
            raise Refused("a savings balance is not negative")
        if self.style is TierStyle.WHOLE_BALANCE:
            return round_money(
                balance.times(self.reached_rate(balance)), balance.currency, mode
            )
        total = Fraction(0)
        for index, tier in enumerate(self.tiers):
            floor = tier.floor.units
            if balance.units <= floor:
                break
            ceiling = (
                self.tiers[index + 1].floor.units
                if index + 1 < len(self.tiers)
                else None
            )
            top = balance.units if ceiling is None else min(ceiling, balance.units)
            slice_units = top - floor
            if slice_units > 0:
                total += Fraction(slice_units) * tier.rate
        return round_money(total, balance.currency, mode)

    def blended_rate(self, balance: Money) -> Fraction | None:
        # The number a saver can actually compare, and for a banded account
        # always below the headline the advertisement leads with.
        if balance.units == 0:
            return None
        return Fraction(self.annual_interest(balance).units, balance.units)

    def beats_headline(self, balance: Money) -> bool:
        blended = self.blended_rate(balance)
        return blended is not None and blended >= self.headline_rate()


def standard_banded(currency: str = "USD") -> SavingsProduct:
    return SavingsProduct(
        name="banded saver",
        tiers=(
            RateTier(Money.zero(currency), Fraction(1, 100)),
            RateTier(Money.of(10000, currency), Fraction(3, 100)),
            RateTier(Money.of(50000, currency), Fraction(5, 100)),
        ),
        style=TierStyle.BANDED,
    )


def standard_whole_balance(currency: str = "USD") -> SavingsProduct:
    return SavingsProduct(
        name="whole balance saver",
        tiers=(
            RateTier(Money.zero(currency), Fraction(1, 100)),
            RateTier(Money.of(10000, currency), Fraction(3, 100)),
            RateTier(Money.of(50000, currency), Fraction(5, 100)),
        ),
        style=TierStyle.WHOLE_BALANCE,
    )
