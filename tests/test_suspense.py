from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.suspense import SuspenseAccount

DAY = datetime.date(2026, 1, 1)
LATER = datetime.date(2026, 3, 1)


def _account() -> SuspenseAccount:
    account = SuspenseAccount("1999", "USD")
    account.park("w1", Money.of(5000, "USD"), DAY, "wire with no reference")
    account.park("w2", Money.of(250, "USD"), DAY, "unmatched customer payment")
    return account


class TestParking:
    def test_parked_money_is_on_the_books(self):
        assert _account().balance() == Money.of(5250, "USD")

    def test_a_duplicate_item_is_refused(self):
        account = _account()
        with pytest.raises(Refused):
            account.park("w1", Money.of(1, "USD"), DAY, "again")

    def test_a_wrong_currency_item_is_refused(self):
        with pytest.raises(Refused):
            _account().park("w3", Money.of(1, "EUR"), DAY, "euros")

    def test_a_nonpositive_item_is_refused(self):
        with pytest.raises(Refused):
            _account().park("w3", Money.zero("USD"), DAY, "nothing")


class TestClearing:
    def test_a_full_clearing_empties_the_item(self):
        account = _account()
        account.get("w2").clear(Money.of(250, "USD"), LATER, "invoice 501", "alice")
        assert account.get("w2").is_cleared()

    def test_a_partial_clearing_leaves_a_remainder(self):
        account = _account()
        item = account.get("w1")
        item.clear(Money.of(3000, "USD"), LATER, "invoice 601", "alice")
        assert item.outstanding() == Money.of(2000, "USD")
        assert not item.is_cleared()

    def test_the_balance_follows_the_clearings(self):
        account = _account()
        account.get("w1").clear(Money.of(3000, "USD"), LATER, "invoice 601", "alice")
        assert account.balance() == Money.of(2250, "USD")

    def test_over_clearing_is_refused(self):
        account = _account()
        with pytest.raises(Refused):
            account.get("w2").clear(Money.of(500, "USD"), LATER, "invoice", "alice")

    def test_a_clearing_must_name_what_it_was(self):
        account = _account()
        with pytest.raises(Refused) as caught:
            account.get("w2").clear(Money.of(10, "USD"), LATER, "  ", "alice")
        assert "two problems where there was one" in str(caught.value)

    def test_a_clearing_must_name_who(self):
        account = _account()
        with pytest.raises(Refused):
            account.get("w2").clear(Money.of(10, "USD"), LATER, "invoice", "  ")


class TestAging:
    def test_open_items_are_listed(self):
        assert len(_account().open_items()) == 2

    def test_stale_items_are_flagged(self):
        account = _account()
        assert len(account.stale_items(LATER)) == 2
        assert account.stale_items(DAY) == []

    def test_the_oldest_open_item_is_named(self):
        account = _account()
        assert account.oldest_open(LATER).id in ("w1", "w2")

    def test_a_cleared_account_is_empty(self):
        account = _account()
        account.get("w1").clear(Money.of(5000, "USD"), LATER, "invoice", "alice")
        account.get("w2").clear(Money.of(250, "USD"), LATER, "invoice", "alice")
        assert account.is_empty()
        assert account.oldest_open(LATER) is None

    def test_an_unknown_item_is_refused(self):
        with pytest.raises(Refused):
            _account().get("nope")
