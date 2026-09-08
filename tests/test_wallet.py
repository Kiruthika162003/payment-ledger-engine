from __future__ import annotations

import datetime

import pytest

from mint.errors import InsufficientFunds, Refused
from mint.money import Money
from mint.wallet import Wallet

DAY = datetime.date(2026, 1, 1)


class TestBalance:
    def test_top_up_and_spend_track_the_balance(self):
        wallet = Wallet("w1", "USD")
        wallet.top_up(Money.of(50, "USD"), DAY)
        wallet.spend(Money.of(20, "USD"), DAY)
        assert wallet.balance() == Money.of(30, "USD")

    def test_balance_is_the_sum_of_movements(self):
        wallet = Wallet("w1", "USD")
        wallet.top_up(Money.of(10, "USD"), DAY)
        wallet.top_up(Money.of(5, "USD"), DAY)
        assert wallet.balance() == Money.of(15, "USD")


class TestRefusals:
    def test_overspend_names_the_shortfall(self):
        wallet = Wallet("w1", "USD")
        wallet.top_up(Money.of(10, "USD"), DAY)
        with pytest.raises(InsufficientFunds) as caught:
            wallet.spend(Money.of(15, "USD"), DAY)
        assert "exceeds" in str(caught.value)

    def test_a_wrong_currency_movement_is_refused(self):
        wallet = Wallet("w1", "USD")
        with pytest.raises(Refused):
            wallet.top_up(Money.of(10, "EUR"), DAY)

    def test_a_nonpositive_movement_is_refused(self):
        wallet = Wallet("w1", "USD")
        with pytest.raises(Refused):
            wallet.top_up(Money.zero("USD"), DAY)


class TestCanAfford:
    def test_can_afford_checks_balance_and_currency(self):
        wallet = Wallet("w1", "USD")
        wallet.top_up(Money.of(10, "USD"), DAY)
        assert wallet.can_afford(Money.of(10, "USD"))
        assert not wallet.can_afford(Money.of(11, "USD"))
        assert not wallet.can_afford(Money.of(1, "EUR"))
