"""Period close: emptying income and expense into equity, once, on purpose.

Income and expense accounts are temporary: they measure a period,
and at its end their balances belong in equity as the period's
profit or loss, leaving the temporary accounts at zero to begin
measuring the next period from scratch. This module performs that
close as a single balanced entry rather than a set of quiet
adjustments, because the close is a real economic event, the
recognition of a period's result, and it should appear in the
ledger as one traceable transaction. The entry posts, against each
income and expense account, exactly the amount that returns it to
zero, and lets the remainder fall to the retained-earnings account,
which by construction is the net income: revenues minus expenses.
The close is currency-scoped, since profit in dollars and profit
in euros are different results that land in different equity
accounts, and it refuses to run when there is nothing to close, so
a double-close on an already-closed period raises rather than
posting an empty ceremony. The net income is returned as a signed
amount, positive for a profit and negative for a loss, so the
caller need not re-derive from the equity movement what the close
already knows.
"""

from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.book import Book
from mint.errors import Refused
from mint.money import Money


def net_income(book: Book, currency: str) -> Money:
    currency = currency.upper()
    total = 0
    for account in book.chart.of_type(AccountType.INCOME):
        if account.currency == currency:
            total += book.ledger.balance_units(account.code)
    for account in book.chart.of_type(AccountType.EXPENSE):
        if account.currency == currency:
            total -= book.ledger.balance_units(account.code)
    return Money.from_minor(total, currency)


def close_period(
    book: Book,
    retained_earnings: str,
    on: datetime.date,
    currency: str | None = None,
) -> Money:
    re_account = book.chart.get(retained_earnings)
    currency = (currency or re_account.currency).upper()
    if re_account.currency != currency:
        raise Refused(
            f"retained earnings {retained_earnings!r} holds "
            f"{re_account.currency}, not {currency}; close each currency to "
            "its own equity account"
        )
    result = net_income(book, currency)
    txn = book.transaction(on, "period close")
    touched = 0
    temporaries = book.chart.of_type(AccountType.INCOME) + book.chart.of_type(
        AccountType.EXPENSE
    )
    for account in temporaries:
        if account.currency != currency:
            continue
        net = book.ledger.raw_debits(account.code) - book.ledger.raw_credits(account.code)
        if net > 0:
            txn.credit(account.code, Money.from_minor(net, currency))
            touched += 1
        elif net < 0:
            txn.debit(account.code, Money.from_minor(-net, currency))
            touched += 1
    if touched == 0:
        raise Refused(
            f"there is nothing to close in {currency}; the period's income "
            "and expense accounts are already at zero"
        )
    if txn.imbalance(currency) != 0:
        txn.balance_against(retained_earnings, currency)
    book.post(txn)
    return result
