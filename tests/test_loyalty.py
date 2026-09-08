from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.loyalty import LoyaltyAccount
from mint.money import Money


def _account() -> LoyaltyAccount:
    # One point per dollar; each point worth one cent on redemption.
    return LoyaltyAccount("m1", "USD", earn_rate=Fraction(1), redeem_value=Fraction(1))


class TestEarn:
    def test_earning_floors_rather_than_rounds(self):
        account = _account()
        points = account.earn_on(Money.of("3.99", "USD"))
        assert points == 3
        assert account.balance() == 3

    def test_points_accumulate(self):
        account = _account()
        account.earn_on(Money.of(10, "USD"))
        account.earn_on(Money.of(5, "USD"))
        assert account.balance() == 15


class TestRedeem:
    def test_redemption_converts_points_to_money(self):
        account = _account()
        account.earn_on(Money.of(100, "USD"))
        value = account.redeem(100)
        assert value == Money.of("1.00", "USD")
        assert account.balance() == 0

    def test_redeeming_beyond_the_balance_is_refused(self):
        account = _account()
        account.earn_on(Money.of(5, "USD"))
        with pytest.raises(Refused) as caught:
            account.redeem(10)
        assert "exceeds" in str(caught.value)


class TestRefusals:
    def test_earning_on_the_wrong_currency_is_refused(self):
        with pytest.raises(Refused):
            _account().earn_on(Money.of(10, "EUR"))

    def test_a_nonpositive_redemption_is_refused(self):
        with pytest.raises(Refused):
            _account().redeem(0)

    def test_a_nonpositive_redeem_value_is_refused(self):
        with pytest.raises(Refused):
            LoyaltyAccount("m", "USD", earn_rate=Fraction(1), redeem_value=Fraction(0))
