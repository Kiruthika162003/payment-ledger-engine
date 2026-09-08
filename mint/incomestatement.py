"""The income statement: revenue earned less expense incurred over a period.

Where the balance sheet is a photograph at an instant, the income
statement is a film of a stretch of time: the revenue earned
between two dates and the expense incurred against it, and the
difference is the period's profit or loss. The distinction that
matters is that this is a flow, not a level, so the statement folds
only the movements dated inside the period rather than balances as
of its end, which is why a first quarter statement queried at
year end still reports the first quarter and not the year to date.
Revenue is shown as the credit movement on income accounts and
expense as the debit movement on expense accounts, each in its
natural positive direction, so the reader is not asked to think in
debits and credits to see what the business earned and spent. The
bottom line, net income, equals the same period's contribution to
equity, and closing that period would move exactly this figure into
retained earnings, which is the tie between the two statements that
makes them one system rather than two independent reports.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from mint.accounts import AccountType
from mint.ledger import Ledger
from mint.money import Money


@dataclass(frozen=True)
class StatementSection:
    title: str
    lines: tuple[tuple[str, str, int], ...]
    total: int


@dataclass(frozen=True)
class IncomeStatement:
    currency: str
    start: datetime.date
    end: datetime.date
    revenue: StatementSection
    expense: StatementSection

    def net_income(self) -> Money:
        return Money.from_minor(self.revenue.total - self.expense.total, self.currency)

    def is_profit(self) -> bool:
        return self.revenue.total > self.expense.total

    def margin_ratio(self) -> float:
        if self.revenue.total == 0:
            return 0.0
        return (self.revenue.total - self.expense.total) / self.revenue.total


def _period_movement(
    ledger: Ledger,
    currency: str,
    account_type: AccountType,
    start: datetime.date,
    end: datetime.date,
) -> tuple[list[tuple[str, str, int]], int]:
    rows: list[tuple[str, str, int]] = []
    total = 0
    debit_normal = account_type is AccountType.EXPENSE
    for account in ledger.chart.of_type(account_type):
        if account.currency != currency:
            continue
        units = 0
        for entry in ledger.entries:
            if entry.date < start or entry.date > end:
                continue
            for posting in entry.postings_for(account.code):
                units += posting.signed_for(debit_normal)
        total += units
        if units != 0:
            rows.append((account.code, account.name, units))
    return rows, total


def income_statement(
    ledger: Ledger, currency: str, start: datetime.date, end: datetime.date
) -> IncomeStatement:
    currency = currency.upper()
    revenue_rows, revenue_total = _period_movement(
        ledger, currency, AccountType.INCOME, start, end
    )
    expense_rows, expense_total = _period_movement(
        ledger, currency, AccountType.EXPENSE, start, end
    )
    return IncomeStatement(
        currency=currency,
        start=start,
        end=end,
        revenue=StatementSection("Revenue", tuple(revenue_rows), revenue_total),
        expense=StatementSection("Expense", tuple(expense_rows), expense_total),
    )
