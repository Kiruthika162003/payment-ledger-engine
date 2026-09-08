"""The balance sheet: assets on one side, liabilities and equity on the other, equal.

A balance sheet is a photograph of what a business owns and owes
at a moment, and its defining property is that the two sides
match, because they are the accounting equation itself: assets
equal liabilities plus equity. The subtlety that trips a naive
report is the current period's profit. Income and expense accounts
are not on the balance sheet, yet their net is real equity the
business has earned and not yet closed, so a balance sheet drawn
mid-period that ignores them shows assets exceeding liabilities and
equity by exactly the unclosed profit and appears, wrongly, not to
balance. This module folds the unclosed net income into the equity
side as its own line, so the sheet balances on any date, before or
after a formal close, which is what lets a business read its
position on a Tuesday without closing the books first. Every figure
is drawn as of a date by folding only the postings up to it, so a
sheet for March is a March sheet even when queried in June, and the
report is currency-scoped since a balance sheet mixing dollars and
yen is a stack of two photographs pretending to be one.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from mint.accounts import AccountType
from mint.ledger import Ledger
from mint.money import Money


@dataclass(frozen=True)
class Section:
    title: str
    lines: tuple[tuple[str, str, int], ...]
    total: int


@dataclass(frozen=True)
class BalanceSheet:
    currency: str
    as_of: datetime.date
    assets: Section
    liabilities: Section
    equity: Section

    def total_assets(self) -> Money:
        return Money.from_minor(self.assets.total, self.currency)

    def total_liabilities_and_equity(self) -> Money:
        return Money.from_minor(self.liabilities.total + self.equity.total, self.currency)

    def balances(self) -> bool:
        return self.assets.total == self.liabilities.total + self.equity.total

    def difference(self) -> int:
        return self.assets.total - (self.liabilities.total + self.equity.total)


def _section(
    ledger: Ledger, currency: str, account_type: AccountType, date: datetime.date
) -> tuple[list[tuple[str, str, int]], int]:
    rows: list[tuple[str, str, int]] = []
    total = 0
    for account in ledger.chart.of_type(account_type):
        if account.currency != currency:
            continue
        units = ledger.balance_units_asof(account.code, date)
        total += units
        if units != 0:
            rows.append((account.code, account.name, units))
    return rows, total


def _current_earnings(ledger: Ledger, currency: str, date: datetime.date) -> int:
    income = _section(ledger, currency, AccountType.INCOME, date)[1]
    expense = _section(ledger, currency, AccountType.EXPENSE, date)[1]
    return income - expense


def balance_sheet(ledger: Ledger, currency: str, as_of: datetime.date) -> BalanceSheet:
    currency = currency.upper()
    asset_rows, asset_total = _section(ledger, currency, AccountType.ASSET, as_of)
    liab_rows, liab_total = _section(ledger, currency, AccountType.LIABILITY, as_of)
    equity_rows, equity_total = _section(ledger, currency, AccountType.EQUITY, as_of)

    earnings = _current_earnings(ledger, currency, as_of)
    if earnings != 0:
        equity_rows = [*equity_rows, ("____", "Current earnings", earnings)]
        equity_total += earnings

    return BalanceSheet(
        currency=currency,
        as_of=as_of,
        assets=Section("Assets", tuple(asset_rows), asset_total),
        liabilities=Section("Liabilities", tuple(liab_rows), liab_total),
        equity=Section("Equity", tuple(equity_rows), equity_total),
    )
