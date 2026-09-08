"""Depreciation: spreading an asset's cost across its life, landing on salvage.

Depreciation recognizes that a machine bought once is used over
years, so its cost is spread across those years rather than
expensed all at once, and the several methods disagree on the
shape of that spread while agreeing on where it ends: the book
value must land on the salvage value at the end of the useful
life, never below it and never above. This module implements the
three methods a ledger meets. Straight line spreads the
depreciable base evenly. Declining balance front-loads it, taking
a fixed fraction of the shrinking book value each year, which
matches assets that lose most of their worth early, and it stops
taking depreciation once the book value reaches salvage rather than
plowing through the floor. Sum-of-the-years-digits front-loads it
more gently by a weighted fraction. All three carry the same
discipline about rounding: the final year takes exactly what
remains to bring the book value to salvage, so the schedule closes
on the right number instead of drifting a few cents past it, and a
salvage value above the cost is refused, since an asset cannot be
worth more scrapped than bought.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import round_money


@dataclass(frozen=True)
class DepRow:
    year: int
    depreciation: int
    accumulated: int
    book_value: int


@dataclass(frozen=True)
class DepSchedule:
    cost: Money
    salvage: Money
    method: str
    rows: tuple[DepRow, ...]

    def total_depreciation(self) -> Money:
        return Money.from_minor(
            sum(r.depreciation for r in self.rows), self.cost.currency
        )

    def ending_book_value(self) -> int:
        return self.rows[-1].book_value if self.rows else self.cost.units


def _guard(cost: Money, salvage: Money, life: int) -> None:
    salvage.same_currency(cost)
    if life < 1:
        raise Refused("an asset's useful life is at least one year")
    if salvage.is_negative():
        raise Refused("a salvage value is not negative")
    if salvage > cost:
        raise Refused("an asset cannot be worth more scrapped than bought")


def straight_line(cost: Money, salvage: Money, life: int) -> DepSchedule:
    _guard(cost, salvage, life)
    base = (cost - salvage).units
    annual = round_money(Fraction(base, life), cost.currency).units
    rows: list[DepRow] = []
    accumulated = 0
    for year in range(1, life + 1):
        dep = base - accumulated if year == life else annual
        accumulated += dep
        rows.append(DepRow(year, dep, accumulated, cost.units - accumulated))
    return DepSchedule(cost, salvage, "straight_line", tuple(rows))


def declining_balance(
    cost: Money, salvage: Money, life: int, factor: Fraction = Fraction(2)
) -> DepSchedule:
    _guard(cost, salvage, life)
    rate = factor / life
    rows: list[DepRow] = []
    book = cost.units
    accumulated = 0
    floor = salvage.units
    for year in range(1, life + 1):
        dep = round_money(Fraction(book) * rate, cost.currency).units
        if book - dep < floor or year == life:
            dep = book - floor
        accumulated += dep
        book -= dep
        rows.append(DepRow(year, dep, accumulated, book))
    return DepSchedule(cost, salvage, "declining_balance", tuple(rows))


def sum_of_years_digits(cost: Money, salvage: Money, life: int) -> DepSchedule:
    _guard(cost, salvage, life)
    base = (cost - salvage).units
    syd = life * (life + 1) // 2
    rows: list[DepRow] = []
    accumulated = 0
    for year in range(1, life + 1):
        weight = life - year + 1
        if year == life:
            dep = base - accumulated
        else:
            dep = round_money(Fraction(base * weight, syd), cost.currency).units
        accumulated += dep
        rows.append(DepRow(year, dep, accumulated, cost.units - accumulated))
    return DepSchedule(cost, salvage, "sum_of_years_digits", tuple(rows))
