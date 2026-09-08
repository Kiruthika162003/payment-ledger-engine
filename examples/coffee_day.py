"""A coffee shop's first day, from the owner's investment to the close.

This example walks one day of a small business through the ledger:
the owner puts in capital, the shop makes a handful of cash sales,
buys supplies on credit, and pays the rent, and then the period is
closed so the day's loss lands in retained earnings. It exercises
the whole spine of the package, the book and its transaction
builder, balances folded from postings, net income, and the close,
and every printed line is pinned in the test suite.
"""

from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.book import Book
from mint.close import close_period, net_income
from mint.money import Money

DAY = datetime.date(2026, 6, 1)


def _dollars(money: Money) -> str:
    return money.format(with_symbol=False)


def run() -> list[str]:
    book = Book()
    book.open("1000", "Cash", AccountType.ASSET, "USD")
    book.open("2000", "Payable", AccountType.LIABILITY, "USD")
    book.open("3000", "Capital", AccountType.EQUITY, "USD")
    book.open("3900", "Retained Earnings", AccountType.EQUITY, "USD")
    book.open("4000", "Sales", AccountType.INCOME, "USD")
    book.open("5000", "Supplies", AccountType.EXPENSE, "USD")
    book.open("5100", "Rent", AccountType.EXPENSE, "USD")

    lines = ["Coffee shop, day one"]

    book.post(
        book.transaction(DAY, "owner invests")
        .debit("1000", Money.of(2000, "USD"))
        .credit("3000", Money.of(2000, "USD"))
    )
    lines.append(f"Owner invests capital: {_dollars(book.balance('3000'))}")

    for price in ("4.50", "3.75", "5.25"):
        book.post(
            book.transaction(DAY, "cash sale")
            .debit("1000", Money.of(price, "USD"))
            .credit("4000", Money.of(price, "USD"))
        )
        lines.append(f"Cash sale: {_dollars(Money.of(price, 'USD'))}")

    book.post(
        book.transaction(DAY, "supplies on credit")
        .debit("5000", Money.of(40, "USD"))
        .credit("2000", Money.of(40, "USD"))
    )
    lines.append(f"Supplies bought on credit: {_dollars(book.balance('2000'))}")

    book.post(
        book.transaction(DAY, "rent")
        .debit("5100", Money.of(500, "USD"))
        .credit("1000", Money.of(500, "USD"))
    )
    lines.append(f"Rent paid, cash now: {_dollars(book.balance('1000'))}")

    lines.append(f"Sales for the day: {_dollars(book.balance('4000'))}")
    lines.append(f"Net income: {_dollars(net_income(book, 'USD'))}")

    result = close_period(book, "3900", DAY)
    lines.append(f"Closed; retained earnings: {_dollars(result)}")
    lines.append(f"Sales after close: {_dollars(book.balance('4000'))}")
    lines.append(f"Books balanced: {book.is_balanced()}")
    return lines


def main() -> None:
    for line in run():
        print(line)


if __name__ == "__main__":
    main()
