"""A money bag: several currencies held together without pretending to be one.

A business with balances in four currencies does not have one
balance, and the temptation to add them into a single reporting
figure is exactly where multi-currency accounting goes wrong,
because the sum depends entirely on the rates used and the rates
change. A money bag holds the positions separately and refuses to
collapse them without being handed the rates and the date to do it,
so a total is always an explicit valuation rather than an
accidental one. Adding money to the bag is exact, since it only
ever adds within a currency, and the bag reports which currencies
it holds and each position, which is what a treasury dashboard
needs before it needs a total. When a total is genuinely wanted the
bag converts each position at a rate from the table, sums, and
reports the date and rates it used, because a valuation without its
rate is a number nobody can reproduce and reproducibility is the
whole difference between a report and a guess. A bag can go
negative in a currency, since owing yen while holding dollars is a
real position rather than an error.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from fractions import Fraction

from mint.conversion import convert
from mint.fxrate import RateTable
from mint.money import Money


@dataclass
class MoneyBag:
    positions: dict[str, int] = field(default_factory=dict)

    def add(self, amount: Money) -> MoneyBag:
        self.positions[amount.currency] = (
            self.positions.get(amount.currency, 0) + amount.units
        )
        return self

    def subtract(self, amount: Money) -> MoneyBag:
        return self.add(-amount)

    def balance(self, currency: str) -> Money:
        currency = currency.upper()
        return Money.from_minor(self.positions.get(currency, 0), currency)

    def currencies(self) -> list[str]:
        return sorted(code for code, units in self.positions.items() if units != 0)

    def is_empty(self) -> bool:
        return all(units == 0 for units in self.positions.values())

    def holdings(self) -> list[Money]:
        return [self.balance(code) for code in self.currencies()]

    def merge(self, other: MoneyBag) -> MoneyBag:
        merged = MoneyBag(dict(self.positions))
        for code, units in other.positions.items():
            merged.positions[code] = merged.positions.get(code, 0) + units
        return merged

    def negate(self) -> MoneyBag:
        return MoneyBag({code: -units for code, units in self.positions.items()})


@dataclass(frozen=True)
class Valuation:
    total: Money
    on: datetime.date
    rates: tuple[tuple[str, Fraction], ...]

    def rate_for(self, currency: str) -> Fraction | None:
        for code, rate in self.rates:
            if code == currency.upper():
                return rate
        return None


def value_in(
    bag: MoneyBag, base: str, rates: RateTable, on: datetime.date
) -> Valuation:
    base = base.upper()
    total = Money.zero(base)
    used: list[tuple[str, Fraction]] = []
    for code in bag.currencies():
        position = bag.balance(code)
        rate = Fraction(1) if code == base else rates.rate_on(code, base, on)
        used.append((code, rate))
        total = total + convert(position, base, rates, on)
    return Valuation(total=total, on=on, rates=tuple(used))
