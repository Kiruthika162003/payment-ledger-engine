from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.customerdeposit import DepositBook, SecurityDeposit
from mint.errors import Refused
from mint.money import Money

TAKEN = datetime.date(2026, 1, 1)
YEAR_LATER = datetime.date(2027, 1, 1)


def _deposit(**kwargs) -> SecurityDeposit:
    base = {
        "id": "D-1",
        "depositor": "tenant",
        "amount": Money.of(2000, "USD"),
        "taken_on": TAKEN,
    }
    base.update(kwargs)
    return SecurityDeposit(**base)


class TestLiability:
    def test_a_deposit_is_a_liability_from_the_start(self):
        assert _deposit().liability_at(TAKEN) == Money.of(2000, "USD")

    def test_interest_accrues_to_the_depositor(self):
        deposit = _deposit(interest_rate=Fraction(5, 100))
        assert deposit.interest_to(YEAR_LATER).is_positive()
        assert deposit.liability_at(YEAR_LATER) > Money.of(2000, "USD")

    def test_no_interest_without_a_rate(self):
        assert _deposit().interest_to(YEAR_LATER).is_zero()

    def test_no_interest_before_it_was_taken(self):
        deposit = _deposit(interest_rate=Fraction(5, 100))
        assert deposit.interest_to(TAKEN).is_zero()


class TestDeductions:
    def test_a_deduction_reduces_what_comes_back(self):
        deposit = _deposit()
        deposit.deduct(Money.of(300, "USD"), YEAR_LATER, "carpet damage")
        statement = deposit.statement(YEAR_LATER)
        assert statement.returned == Money.of(1700, "USD")

    def test_a_deduction_needs_a_reason(self):
        with pytest.raises(Refused) as caught:
            _deposit().deduct(Money.of(100, "USD"), YEAR_LATER, "  ")
        assert "costs more than the deposit" in str(caught.value)

    def test_deductions_beyond_the_deposit_stay_recoverable(self):
        deposit = _deposit()
        deposit.deduct(Money.of(2500, "USD"), YEAR_LATER, "major damage")
        statement = deposit.statement(YEAR_LATER)
        assert statement.returned.is_zero()
        assert statement.still_recoverable == Money.of(500, "USD")

    def test_the_statement_reconciles(self):
        deposit = _deposit(interest_rate=Fraction(5, 100))
        deposit.deduct(Money.of(300, "USD"), YEAR_LATER, "cleaning")
        assert deposit.statement(YEAR_LATER).reconciles()

    def test_a_nonpositive_deduction_is_refused(self):
        with pytest.raises(Refused):
            _deposit().deduct(Money.zero("USD"), YEAR_LATER, "nothing")


class TestReturn:
    def test_returning_closes_the_deposit(self):
        deposit = _deposit()
        statement = deposit.give_back(YEAR_LATER)
        assert deposit.is_returned()
        assert statement.returned == Money.of(2000, "USD")

    def test_returning_twice_is_refused(self):
        deposit = _deposit()
        deposit.give_back(YEAR_LATER)
        with pytest.raises(Refused):
            deposit.give_back(YEAR_LATER)

    def test_deducting_after_return_is_refused(self):
        deposit = _deposit()
        deposit.give_back(YEAR_LATER)
        with pytest.raises(Refused):
            deposit.deduct(Money.of(10, "USD"), YEAR_LATER, "late claim")

    def test_interest_is_included_in_the_return(self):
        deposit = _deposit(interest_rate=Fraction(5, 100))
        statement = deposit.give_back(YEAR_LATER)
        assert statement.returned > Money.of(2000, "USD")


class TestBook:
    def _book(self) -> DepositBook:
        book = DepositBook("USD")
        book.take(_deposit())
        book.take(_deposit(id="D-2", amount=Money.of(1500, "USD")))
        return book

    def test_the_book_totals_what_is_held(self):
        assert self._book().total_held(TAKEN) == Money.of(3500, "USD")

    def test_a_returned_deposit_leaves_the_total(self):
        book = self._book()
        book.deposits[0].give_back(YEAR_LATER)
        assert book.total_held(YEAR_LATER) == Money.of(1500, "USD")
        assert len(book.outstanding()) == 1

    def test_a_duplicate_deposit_is_refused(self):
        book = self._book()
        with pytest.raises(Refused):
            book.take(_deposit())

    def test_a_wrong_currency_deposit_is_refused(self):
        book = self._book()
        with pytest.raises(Refused):
            book.take(_deposit(id="D-9", amount=Money.of(100, "EUR")))

    def test_a_nonpositive_deposit_is_refused(self):
        with pytest.raises(Refused):
            _deposit(amount=Money.zero("USD"))
