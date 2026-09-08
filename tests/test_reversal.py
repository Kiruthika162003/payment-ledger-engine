from __future__ import annotations

import datetime

import pytest

from mint.accounts import AccountType, Side
from mint.book import Book
from mint.entry import entry
from mint.errors import Refused
from mint.money import Money
from mint.posting import credit, debit
from mint.reversal import nets_to_zero, reverse_entry

DAY = datetime.date(2026, 1, 10)
LATER = datetime.date(2026, 2, 1)


def _entry():
    return entry(
        [debit("1000", Money.of(100, "USD")), credit("4000", Money.of(100, "USD"))],
        DAY,
        memo="a sale",
        ref="INV-1",
    )


class TestMirror:
    def test_every_side_is_flipped(self):
        reversal = reverse_entry(_entry(), LATER)
        assert reversal.postings[0].side is Side.CREDIT
        assert reversal.postings[1].side is Side.DEBIT

    def test_the_pair_nets_to_zero(self):
        original = _entry()
        assert nets_to_zero(original, reverse_entry(original, LATER))

    def test_the_reference_is_carried(self):
        reversal = reverse_entry(_entry(), LATER)
        assert reversal.ref == "INV-1"
        assert "reversal" in reversal.tags

    def test_the_memo_names_the_original(self):
        assert reverse_entry(_entry(), LATER).memo == "reversal of a sale"

    def test_an_explicit_memo_is_kept(self):
        assert reverse_entry(_entry(), LATER, memo="fixing a typo").memo == "fixing a typo"


class TestInLedger:
    def test_reversing_returns_the_balances_to_where_they_were(self):
        book = Book()
        book.open("1000", "Cash", AccountType.ASSET, "USD")
        book.open("4000", "Sales", AccountType.INCOME, "USD")
        original = book.post_entry(_entry())
        assert book.balance("1000") == Money.of(100, "USD")
        book.post_entry(reverse_entry(original, LATER))
        assert book.balance("1000").is_zero()
        assert book.balance("4000").is_zero()
        assert book.is_balanced()

    def test_reversing_a_reversal_restores_the_effect(self):
        original = _entry()
        first = reverse_entry(original, LATER)
        second = reverse_entry(first, LATER)
        assert second.postings[0].side is Side.DEBIT


class TestRefusals:
    def test_backdating_a_reversal_is_refused(self):
        with pytest.raises(Refused) as caught:
            reverse_entry(_entry(), datetime.date(2026, 1, 1))
        assert "already been reported" in str(caught.value)
