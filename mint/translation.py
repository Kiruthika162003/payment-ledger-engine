"""Translating a foreign subsidiary: three rates, and the difference that must go somewhere.

A subsidiary keeping its books in another currency has to be
restated into the group's currency, and the rule is not one rate
but three. Assets and liabilities translate at the closing rate,
because that is what they are worth on the balance sheet date.
Income and expenses translate at the average rate for the period,
because they accrued throughout it and the closing rate would
misstate a year of trading by whatever happened in December. Equity
translates at the historical rate at which it was contributed,
since the shareholders put in what they put in. Three different
rates on figures that balanced in the original currency will not
balance in the new one, and the difference is not an error to hunt
down; it is the cumulative translation adjustment, a real component
of equity that exists precisely because rates moved. This module
computes all three translations and the residual, and the residual
is derived as the amount that makes the translated balance sheet
balance rather than computed independently, because deriving it is
what guarantees the statements tie out.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.conversion import convert_at
from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class ForeignStatements:
    assets: Money
    liabilities: Money
    contributed_equity: Money
    retained_earnings: Money
    revenue: Money
    expenses: Money

    def __post_init__(self) -> None:
        base = self.assets.currency
        for value in (
            self.liabilities,
            self.contributed_equity,
            self.retained_earnings,
            self.revenue,
            self.expenses,
        ):
            if value.currency != base:
                raise Refused("a subsidiary's statements are in one currency")

    def balances(self) -> bool:
        equity = self.contributed_equity + self.retained_earnings
        return self.assets == self.liabilities + equity


@dataclass(frozen=True)
class TranslatedStatements:
    assets: Money
    liabilities: Money
    contributed_equity: Money
    retained_earnings: Money
    revenue: Money
    expenses: Money
    translation_adjustment: Money

    def net_income(self) -> Money:
        return self.revenue - self.expenses

    def total_equity(self) -> Money:
        return (
            self.contributed_equity
            + self.retained_earnings
            + self.translation_adjustment
        )

    def balances(self) -> bool:
        return self.assets == self.liabilities + self.total_equity()


def translate(
    statements: ForeignStatements,
    base: str,
    closing_rate: Fraction,
    average_rate: Fraction,
    historical_rate: Fraction,
) -> TranslatedStatements:
    base = base.upper()
    if statements.assets.currency == base:
        raise Refused(
            "translation restates a foreign subsidiary; these statements are "
            "already in the group currency"
        )
    for rate in (closing_rate, average_rate, historical_rate):
        if rate <= 0:
            raise Refused("a translation rate is a positive ratio")

    assets = convert_at(statements.assets, base, closing_rate)
    liabilities = convert_at(statements.liabilities, base, closing_rate)
    contributed = convert_at(statements.contributed_equity, base, historical_rate)
    retained = convert_at(statements.retained_earnings, base, historical_rate)
    revenue = convert_at(statements.revenue, base, average_rate)
    expenses = convert_at(statements.expenses, base, average_rate)

    # Derived, not computed independently: the plug that makes it balance.
    adjustment = assets - liabilities - contributed - retained
    return TranslatedStatements(
        assets=assets,
        liabilities=liabilities,
        contributed_equity=contributed,
        retained_earnings=retained,
        revenue=revenue,
        expenses=expenses,
        translation_adjustment=adjustment,
    )
