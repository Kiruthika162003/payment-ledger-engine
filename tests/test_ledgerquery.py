from __future__ import annotations

import datetime

import pytest

from mint.accounts import AccountType
from mint.book import Book
from mint.errors import Refused
from mint.ledgerquery import query
from mint.money import Money

JAN = datetime.date(2026, 1, 10)
FEB = datetime.date(2026, 2, 10)
MAR = datetime.date(2026, 3, 10)


def _book() -> Book:
    book = Book()
    book.open("1000", "Cash", AccountType.ASSET, "USD")
    book.open("4000", "Sales", AccountType.INCOME, "USD")
    book.open("5000", "Rent", AccountType.EXPENSE, "USD")
    book.post(
        book.transaction(JAN, "january sale", "INV-1")
        .debit("1000", Money.of(100, "USD"))
        .credit("4000", Money.of(100, "USD"))
    )
    book.post(
        book.transaction(FEB, "february sale", "INV-2")
        .debit("1000", Money.of(500, "USD"))
        .credit("4000", Money.of(500, "USD"))
    )
    book.post(
        book.transaction(MAR, "march rent", "EXP-1")
        .debit("5000", Money.of(300, "USD"))
        .credit("1000", Money.of(300, "USD"))
    )
    return book


class TestFilters:
    def test_filtering_by_account(self):
        result = query("USD").touching("5000").run(_book().ledger)
        assert result.count() == 1

    def test_filtering_by_date_range(self):
        result = query("USD").between(JAN, FEB).run(_book().ledger)
        assert result.count() == 2

    def test_filtering_by_reference(self):
        result = query("USD").referenced("INV-2").run(_book().ledger)
        assert result.count() == 1

    def test_filtering_by_memo(self):
        result = query("USD").memo_contains("SALE").run(_book().ledger)
        assert result.count() == 2

    def test_filtering_by_amount(self):
        result = query("USD").at_least(Money.of(200, "USD")).run(_book().ledger)
        assert result.count() == 2

    def test_an_upper_bound(self):
        result = query("USD").at_most(Money.of(200, "USD")).run(_book().ledger)
        assert result.count() == 1


class TestComposition:
    def test_criteria_combine_as_an_and(self):
        result = (
            query("USD")
            .touching("1000")
            .between(JAN, FEB)
            .at_least(Money.of(200, "USD"))
            .run(_book().ledger)
        )
        assert result.count() == 1
        assert result.refs() == ("INV-2",)

    def test_the_query_describes_itself(self):
        described = query("USD").touching("1000").tagged("recurring").describe()
        assert "touching 1000" in described
        assert " and " in described

    def test_an_impossible_combination_returns_nothing(self):
        result = (
            query("USD").referenced("INV-1").referenced("INV-2").run(_book().ledger)
        )
        assert result.is_empty()
        assert result.count() == 0


class TestTotals:
    def test_the_result_carries_its_totals(self):
        result = query("USD").touching("4000").run(_book().ledger)
        assert result.total_credits() == Money.of(600, "USD")
        assert result.total_debits() == Money.of(600, "USD")

    def test_the_dates_are_listed(self):
        result = query("USD").touching("1000").run(_book().ledger)
        assert result.dates() == (JAN, FEB, MAR)

    def test_refs_are_listed_once(self):
        result = query("USD").touching("1000").run(_book().ledger)
        assert result.refs() == ("EXP-1", "INV-1", "INV-2")


class TestRefusals:
    def test_a_query_with_no_criteria_is_refused(self):
        with pytest.raises(Refused) as caught:
            query("USD").run(_book().ledger)
        assert "rarely what anyone meant" in str(caught.value)

    def test_a_backward_date_range_is_refused(self):
        with pytest.raises(Refused):
            query("USD").between(MAR, JAN)

    def test_a_tag_filter_matches_nothing_here(self):
        result = query("USD").tagged("recurring").run(_book().ledger)
        assert result.is_empty()
