"""Progressive brackets: the rate applies to the slice, not to the whole income.

The most widespread misunderstanding about income tax is that
crossing into a higher bracket taxes all of your income at the
higher rate, and the belief is common enough that people turn down
raises over it. It is wrong: each bracket's rate applies only to
the income inside that bracket, so a raise can never reduce
take-home pay. This module implements it that way and offers both
figures that make the distinction visible, the marginal rate, which
is the rate on the next dollar earned, and the effective rate,
which is the tax divided by the whole income and is always lower
than the marginal rate whenever more than one bracket is in play.
Brackets must start at zero and increase without gaps, since a gap
leaves income with no rate at all, and the top bracket is
open-ended because there is no ceiling on income. The arithmetic
stays in exact fractions and rounds once at the end, so a tax table
built from these brackets sums to the same total whichever way it
is aggregated.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


@dataclass(frozen=True)
class Bracket:
    floor: Money
    rate: Fraction

    def __post_init__(self) -> None:
        if self.rate < 0 or self.rate >= 1:
            raise Refused("a tax rate is a fraction below one")
        if self.floor.is_negative():
            raise Refused("a bracket floor is not negative")


@dataclass(frozen=True)
class BracketResult:
    income: Money
    tax: Money
    slices: tuple[tuple[str, int], ...]

    def net(self) -> Money:
        return self.income - self.tax

    def effective_rate(self) -> Fraction | None:
        if self.income.units == 0:
            return None
        return Fraction(self.tax.units, self.income.units)


@dataclass(frozen=True)
class BracketTable:
    brackets: tuple[Bracket, ...]

    def __post_init__(self) -> None:
        if not self.brackets:
            raise Refused("a bracket table needs at least one bracket")
        if self.brackets[0].floor.units != 0:
            raise Refused("the first bracket starts at zero income")
        floors = [bracket.floor.units for bracket in self.brackets]
        if floors != sorted(floors) or len(set(floors)) != len(floors):
            raise Refused("bracket floors must strictly increase")

    def currency(self) -> str:
        return self.brackets[0].floor.currency

    def marginal_rate(self, income: Money) -> Fraction:
        rate = self.brackets[0].rate
        for bracket in self.brackets:
            if income.units >= bracket.floor.units:
                rate = bracket.rate
        return rate

    def tax_on(self, income: Money, mode: Rounding = Rounding.HALF_EVEN) -> BracketResult:
        if income.currency != self.currency():
            raise Refused(
                f"this table is in {self.currency()}, not {income.currency}"
            )
        if income.is_negative():
            raise Refused("income taxed through brackets is not negative")
        total = Fraction(0)
        slices: list[tuple[str, int]] = []
        for index, bracket in enumerate(self.brackets):
            floor = bracket.floor.units
            if income.units <= floor:
                break
            ceiling = (
                self.brackets[index + 1].floor.units
                if index + 1 < len(self.brackets)
                else None
            )
            top = income.units if ceiling is None else min(ceiling, income.units)
            band = top - floor
            if band <= 0:
                continue
            piece = Fraction(band) * bracket.rate
            total += piece
            label = f"{float(bracket.rate * 100):g}%"
            slices.append((label, round_money(piece, income.currency, mode).units))
        return BracketResult(
            income=income,
            tax=round_money(total, income.currency, mode),
            slices=tuple(slices),
        )

    def take_home(self, income: Money) -> Money:
        return self.tax_on(income).net()

    def raise_is_never_a_loss(self, before: Money, after: Money) -> bool:
        # The property people disbelieve, stated as something checkable.
        return self.take_home(after) >= self.take_home(before)
