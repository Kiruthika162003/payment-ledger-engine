from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.book import Book
from mint.money import Money
from mint.snapshot import compare, take

MARCH = datetime.date(2026, 3, 31)
TAKEN = datetime.datetime(2026, 4, 1, 9, 0)
LATER = datetime.datetime(2026, 6, 1, 9, 0)
FEB = datetime.date(2026, 2, 15)


def _book() -> Book:
    book = Book()
    book.open("1000", "Cash", AccountType.ASSET, "USD")
    book.open("4000", "Sales", AccountType.INCOME, "USD")
    book.post(
        book.transaction(FEB).debit("1000", Money.of(100, "USD")).credit(
            "4000", Money.of(100, "USD")
        )
    )
    return book


class TestTaking:
    def test_a_snapshot_records_the_balances(self):
        snap = take(_book().ledger, "march", MARCH, TAKEN, "USD")
        assert snap.balance_of("1000") == 10000

    def test_it_records_the_entry_count(self):
        snap = take(_book().ledger, "march", MARCH, TAKEN, "USD")
        assert snap.entry_count == 1

    def test_it_lists_the_accounts(self):
        snap = take(_book().ledger, "march", MARCH, TAKEN, "USD")
        assert snap.accounts() == ("1000", "4000")

    def test_an_unknown_account_has_no_balance(self):
        snap = take(_book().ledger, "march", MARCH, TAKEN, "USD")
        assert snap.balance_of("9999") is None


class TestComparison:
    def test_an_unchanged_ledger_diffs_to_nothing(self):
        book = _book()
        first = take(book.ledger, "march", MARCH, TAKEN, "USD")
        second = take(book.ledger, "march again", MARCH, LATER, "USD")
        assert compare(first, second).is_identical()

    def test_a_backdated_entry_shows_as_a_change(self):
        book = _book()
        first = take(book.ledger, "march", MARCH, TAKEN, "USD")
        book.post(
            book.transaction(FEB, "backdated").debit(
                "1000", Money.of(50, "USD")
            ).credit("4000", Money.of(50, "USD"))
        )
        second = take(book.ledger, "march again", MARCH, LATER, "USD")
        diff = compare(first, second)
        assert not diff.is_identical()
        assert ("1000", 10000, 15000) in diff.changed
        assert diff.entries_added == 1

    def test_a_new_account_is_reported_separately(self):
        book = _book()
        first = take(book.ledger, "march", MARCH, TAKEN, "USD")
        book.open("5000", "Rent", AccountType.EXPENSE, "USD")
        second = take(book.ledger, "march again", MARCH, LATER, "USD")
        diff = compare(first, second)
        assert diff.added_accounts == ("5000",)
        assert diff.changed == ()

    def test_the_largest_change_is_named(self):
        book = _book()
        first = take(book.ledger, "march", MARCH, TAKEN, "USD")
        book.post(
            book.transaction(FEB).debit("1000", Money.of(500, "USD")).credit(
                "4000", Money.of(500, "USD")
            )
        )
        second = take(book.ledger, "again", MARCH, LATER, "USD")
        assert compare(first, second).largest_change()[0] in ("1000", "4000")

    def test_no_largest_change_when_identical(self):
        book = _book()
        first = take(book.ledger, "a", MARCH, TAKEN, "USD")
        second = take(book.ledger, "b", MARCH, LATER, "USD")
        assert compare(first, second).largest_change() is None
