from __future__ import annotations

import datetime

import pytest

from mint.errors import InsufficientFunds, Refused
from mint.giftcard import GiftCard
from mint.money import Money

ISSUED = datetime.date(2026, 1, 1)
EXPIRY = datetime.date(2026, 6, 1)
LATER = datetime.date(2026, 7, 1)


def _card(amount: str = "50.00", expires=EXPIRY) -> GiftCard:
    return GiftCard("gc1", Money.of(amount, "USD"), ISSUED, expires=expires)


class TestRedeem:
    def test_partial_redemptions_draw_the_balance_down(self):
        card = _card()
        card.redeem(Money.of(20, "USD"), ISSUED)
        assert card.balance() == Money.of(30, "USD")

    def test_redeeming_past_the_balance_is_refused(self):
        card = _card()
        with pytest.raises(InsufficientFunds):
            card.redeem(Money.of(60, "USD"), ISSUED)

    def test_it_is_live_until_spent_or_expired(self):
        card = _card()
        assert card.is_live(ISSUED)
        card.redeem(Money.of(50, "USD"), ISSUED)
        assert not card.is_live(ISSUED)


class TestExpiry:
    def test_redeeming_after_expiry_is_refused(self):
        card = _card()
        with pytest.raises(Refused) as caught:
            card.redeem(Money.of(10, "USD"), LATER)
        assert "forfeited" in str(caught.value)

    def test_the_remaining_balance_is_forfeited_after_expiry(self):
        card = _card()
        card.redeem(Money.of(20, "USD"), ISSUED)
        assert card.forfeited(LATER) == Money.of(30, "USD")
        assert card.forfeited(ISSUED).is_zero()


class TestConstruction:
    def test_a_nonpositive_load_is_refused(self):
        with pytest.raises(Refused):
            GiftCard("x", Money.zero("USD"), ISSUED)
