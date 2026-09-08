"""Financial ratios: the handful of quotients that summarize a balance sheet.

A ratio is a quotient, which means it has one interesting failure
mode and this module is mostly about that failure mode. Dividing by
zero is not an edge case here, it is a real state of a real
business: a company with no current liabilities has an undefined
current ratio, not an infinite one, and a company with no revenue
has an undefined margin rather than a margin of zero. Returning
zero in those cases is the lie that shows up on a dashboard as a
solvent company looking distressed or a distressed one looking
fine, so every ratio here returns None when its denominator is zero
and the caller decides how to present the absence. The ratios
themselves are the standard set: liquidity, whether short-term
obligations can be met; leverage, how much of the business is
funded by debt; and profitability, what fraction of revenue
survives to the bottom line. Each is computed from figures the
ledger already produces rather than from separately maintained
numbers, so a ratio can never disagree with the statements it
summarizes.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money


def _ratio(numerator: int, denominator: int) -> Fraction | None:
    if denominator == 0:
        return None
    return Fraction(numerator, denominator)


@dataclass(frozen=True)
class FinancialPosition:
    current_assets: Money
    inventory: Money
    current_liabilities: Money
    total_assets: Money
    total_liabilities: Money
    equity: Money
    revenue: Money
    net_income: Money

    def __post_init__(self) -> None:
        base = self.current_assets.currency
        for field_value in (
            self.inventory,
            self.current_liabilities,
            self.total_assets,
            self.total_liabilities,
            self.equity,
            self.revenue,
            self.net_income,
        ):
            if field_value.currency != base:
                raise Refused(
                    "a ratio set mixes currencies; every figure must be in the "
                    "same currency for the quotients to mean anything"
                )

    def current_ratio(self) -> Fraction | None:
        return _ratio(self.current_assets.units, self.current_liabilities.units)

    def quick_ratio(self) -> Fraction | None:
        liquid = self.current_assets.units - self.inventory.units
        return _ratio(liquid, self.current_liabilities.units)

    def working_capital(self) -> Money:
        return self.current_assets - self.current_liabilities

    def debt_to_equity(self) -> Fraction | None:
        return _ratio(self.total_liabilities.units, self.equity.units)

    def equity_ratio(self) -> Fraction | None:
        return _ratio(self.equity.units, self.total_assets.units)

    def net_margin(self) -> Fraction | None:
        return _ratio(self.net_income.units, self.revenue.units)

    def return_on_equity(self) -> Fraction | None:
        return _ratio(self.net_income.units, self.equity.units)

    def return_on_assets(self) -> Fraction | None:
        return _ratio(self.net_income.units, self.total_assets.units)

    def is_solvent(self) -> bool:
        return self.total_assets >= self.total_liabilities

    def summary(self) -> dict[str, Fraction | None]:
        return {
            "current_ratio": self.current_ratio(),
            "quick_ratio": self.quick_ratio(),
            "debt_to_equity": self.debt_to_equity(),
            "equity_ratio": self.equity_ratio(),
            "net_margin": self.net_margin(),
            "return_on_equity": self.return_on_equity(),
            "return_on_assets": self.return_on_assets(),
        }
