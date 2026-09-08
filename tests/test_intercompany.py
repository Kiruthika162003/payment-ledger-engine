from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.intercompany import IntercompanyLedger
from mint.money import Money


def _matched() -> IntercompanyLedger:
    ledger = IntercompanyLedger("USD")
    ledger.record("P", "S", Money.of(1000, "USD"), "receivable")
    ledger.record("S", "P", Money.of(1000, "USD"), "payable")
    return ledger


class TestReciprocity:
    def test_matched_balances_are_reciprocal(self):
        assert _matched().is_reciprocal()
        assert _matched().mismatches() == []

    def test_a_mismatch_is_reported_with_the_difference(self):
        ledger = IntercompanyLedger("USD")
        ledger.record("P", "S", Money.of(1000, "USD"), "receivable")
        ledger.record("S", "P", Money.of(900, "USD"), "payable")
        mismatch = ledger.mismatches()[0]
        assert mismatch.difference() == Money.of(100, "USD")
        assert not ledger.is_reciprocal()

    def test_a_missing_side_is_a_mismatch(self):
        ledger = IntercompanyLedger("USD")
        ledger.record("P", "S", Money.of(1000, "USD"), "receivable")
        assert len(ledger.mismatches()) == 1


class TestElimination:
    def test_matched_balances_are_eliminable(self):
        assert _matched().eliminable() == Money.of(1000, "USD")

    def test_a_mismatched_pair_is_not_quietly_eliminated(self):
        ledger = IntercompanyLedger("USD")
        ledger.record("P", "S", Money.of(1000, "USD"), "receivable")
        ledger.record("S", "P", Money.of(900, "USD"), "payable")
        assert ledger.eliminable().is_zero()

    def test_pairs_are_listed_once(self):
        assert _matched().pairs() == [("P", "S")]


class TestRefusals:
    def test_a_self_balance_is_refused(self):
        with pytest.raises(Refused):
            IntercompanyLedger("USD").record("P", "P", Money.of(1, "USD"), "receivable")

    def test_an_unknown_kind_is_refused(self):
        with pytest.raises(Refused):
            IntercompanyLedger("USD").record("P", "S", Money.of(1, "USD"), "sideways")

    def test_a_wrong_currency_is_refused(self):
        with pytest.raises(Refused):
            IntercompanyLedger("USD").record("P", "S", Money.of(1, "EUR"), "receivable")

    def test_a_nonpositive_balance_is_refused(self):
        with pytest.raises(Refused):
            IntercompanyLedger("USD").record("P", "S", Money.zero("USD"), "receivable")
