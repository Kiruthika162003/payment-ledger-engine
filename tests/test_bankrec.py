from __future__ import annotations

import pytest

from mint.bankrec import BankReconciliation
from mint.errors import Refused
from mint.money import Money


def _rec(bank: str = "5000.00", book: str = "4800.00") -> BankReconciliation:
    return BankReconciliation(
        currency="USD",
        bank_balance=Money.of(bank, "USD"),
        book_balance=Money.of(book, "USD"),
    )


class TestWalking:
    def test_a_clean_reconciliation(self):
        rec = _rec()
        rec.add_deposit_in_transit("late deposit", Money.of(500, "USD"))
        rec.add_outstanding_cheque("cheque 101", Money.of(700, "USD"))
        # bank 5000 + 500 - 700 = 4800, which equals the book balance.
        assert rec.adjusted_bank() == Money.of(4800, "USD")
        assert rec.reconciles()

    def test_bank_charges_reduce_the_book_side(self):
        rec = _rec(bank="4800.00", book="4830.00")
        rec.add_bank_charge("monthly fee", Money.of(30, "USD"))
        assert rec.adjusted_book() == Money.of(4800, "USD")
        assert rec.reconciles()

    def test_bank_credits_raise_the_book_side(self):
        rec = _rec(bank="4850.00", book="4800.00")
        rec.add_bank_credit("interest earned", Money.of(50, "USD"))
        assert rec.adjusted_book() == Money.of(4850, "USD")
        assert rec.reconciles()

    def test_a_book_error_adjusts_the_book_side(self):
        rec = _rec(bank="5000.00", book="4900.00")
        rec.add_book_error("transposed digit", Money.of(100, "USD"))
        assert rec.reconciles()


class TestResidual:
    def test_an_unexplained_difference_survives(self):
        rec = _rec()
        rec.add_deposit_in_transit("late deposit", Money.of(100, "USD"))
        assert not rec.reconciles()
        assert rec.difference() == Money.of(300, "USD")

    def test_the_difference_is_the_size_of_the_problem(self):
        rec = _rec(bank="1000.00", book="900.00")
        assert rec.difference() == Money.of(100, "USD")

    def test_an_item_on_the_wrong_side_moves_it_by_twice(self):
        # A deposit in transit put on the book side instead of the bank side
        # moves the difference by two hundred, not one hundred.
        right = _rec(bank="1000.00", book="1100.00")
        right.add_deposit_in_transit("deposit", Money.of(100, "USD"))
        wrong = _rec(bank="1000.00", book="1100.00")
        wrong.add_bank_credit("deposit", Money.of(100, "USD"))
        gap = right.difference() - wrong.difference()
        assert gap == Money.of(200, "USD")


class TestSummary:
    def test_the_summary_lists_every_figure(self):
        rec = _rec()
        rec.add_deposit_in_transit("late deposit", Money.of(500, "USD"))
        summary = rec.summary()
        assert summary["deposits in transit"] == Money.of(500, "USD")
        assert summary["adjusted bank"] == Money.of(5500, "USD")
        assert "difference" in summary


class TestRefusals:
    def test_a_negative_item_is_refused(self):
        with pytest.raises(Refused) as caught:
            _rec().add_bank_charge("odd", Money.of("-5.00", "USD"))
        assert "its side decides the direction" in str(caught.value)

    def test_a_wrong_currency_item_is_refused(self):
        with pytest.raises(Refused):
            _rec().add_bank_charge("euro fee", Money.of(5, "EUR"))

    def test_mismatched_balances_are_refused(self):
        with pytest.raises(Refused):
            BankReconciliation(
                currency="USD",
                bank_balance=Money.of(100, "USD"),
                book_balance=Money.of(100, "EUR"),
            )
