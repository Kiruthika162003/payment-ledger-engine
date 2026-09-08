from __future__ import annotations

import datetime

import pytest

from mint.bankaccount import BankAccount
from mint.errors import InsufficientFunds, Refused
from mint.money import Money

DAY = datetime.date(2026, 1, 1)
NEXT = datetime.date(2026, 1, 2)
LATER = datetime.date(2026, 1, 10)


def _account(**kwargs) -> BankAccount:
    return BankAccount("acct-1", "USD", **kwargs)


class TestTwoBalances:
    def test_an_uncleared_deposit_is_not_available(self):
        account = _account()
        account.deposit(Money.of(500, "USD"), DAY, available_on=LATER)
        assert account.ledger_balance(DAY) == Money.of(500, "USD")
        assert account.available_balance(DAY).is_zero()

    def test_it_becomes_available_on_its_date(self):
        account = _account()
        account.deposit(Money.of(500, "USD"), DAY, available_on=LATER)
        assert account.available_balance(LATER) == Money.of(500, "USD")

    def test_a_same_day_deposit_is_available_at_once(self):
        account = _account()
        account.deposit(Money.of(100, "USD"), DAY)
        assert account.available_balance(DAY) == Money.of(100, "USD")


class TestHolds:
    def test_a_hold_reduces_available_but_not_ledger(self):
        account = _account()
        account.deposit(Money.of(500, "USD"), DAY)
        account.place_hold("h1", Money.of(200, "USD"), DAY)
        assert account.available_balance(DAY) == Money.of(300, "USD")
        assert account.ledger_balance(DAY) == Money.of(500, "USD")

    def test_releasing_a_hold_restores_availability(self):
        account = _account()
        account.deposit(Money.of(500, "USD"), DAY)
        account.place_hold("h1", Money.of(200, "USD"), DAY)
        account.release_hold("h1")
        assert account.available_balance(DAY) == Money.of(500, "USD")

    def test_an_expired_hold_stops_counting(self):
        account = _account()
        account.deposit(Money.of(500, "USD"), DAY)
        account.place_hold("h1", Money.of(200, "USD"), DAY, expires=NEXT)
        assert account.available_balance(LATER) == Money.of(500, "USD")

    def test_a_hold_beyond_available_is_refused(self):
        account = _account()
        account.deposit(Money.of(100, "USD"), DAY)
        with pytest.raises(InsufficientFunds):
            account.place_hold("h1", Money.of(200, "USD"), DAY)

    def test_a_double_release_is_refused(self):
        account = _account()
        account.deposit(Money.of(500, "USD"), DAY)
        account.place_hold("h1", Money.of(100, "USD"), DAY)
        account.release_hold("h1")
        with pytest.raises(Refused):
            account.release_hold("h1")


class TestSpending:
    def test_spending_uncleared_money_is_refused(self):
        account = _account()
        account.deposit(Money.of(500, "USD"), DAY, available_on=LATER)
        with pytest.raises(InsufficientFunds) as caught:
            account.withdraw(Money.of(100, "USD"), DAY)
        assert "not spendable" in str(caught.value)

    def test_an_overdraft_limit_extends_spending_power(self):
        account = _account(overdraft_limit=Money.of(200, "USD"))
        account.deposit(Money.of(100, "USD"), DAY)
        account.withdraw(Money.of(250, "USD"), DAY)
        assert account.is_overdrawn(DAY)

    def test_spending_past_the_overdraft_limit_is_refused(self):
        account = _account(overdraft_limit=Money.of(200, "USD"))
        account.deposit(Money.of(100, "USD"), DAY)
        with pytest.raises(InsufficientFunds):
            account.withdraw(Money.of(400, "USD"), DAY)


class TestRefusals:
    def test_availability_before_deposit_is_refused(self):
        with pytest.raises(Refused):
            _account().deposit(Money.of(10, "USD"), LATER, available_on=DAY)

    def test_a_wrong_currency_movement_is_refused(self):
        with pytest.raises(Refused):
            _account().deposit(Money.of(10, "EUR"), DAY)
