from __future__ import annotations

from fractions import Fraction

import pytest

from mint.deferredtax import (
    DeferredTaxAccount,
    PermanentDifference,
    TemporaryDifference,
)
from mint.errors import Refused
from mint.money import Money


def _account(rate: Fraction = Fraction(25, 100)) -> DeferredTaxAccount:
    return DeferredTaxAccount(currency="USD", tax_rate=rate)


def _asset_difference() -> TemporaryDifference:
    # Books carry 100000, tax base is 60000 after faster tax depreciation.
    return TemporaryDifference(
        "plant", Money.of(100000, "USD"), Money.of(60000, "USD")
    )


class TestDifferences:
    def test_an_asset_above_its_tax_base_defers_tax(self):
        difference = _asset_difference()
        assert difference.difference() == Money.of(40000, "USD")
        assert difference.creates_liability()

    def test_an_asset_below_its_tax_base_creates_an_asset(self):
        difference = TemporaryDifference(
            "provision", Money.of(50000, "USD"), Money.of(70000, "USD")
        )
        assert not difference.creates_liability()

    def test_a_liability_side_difference_reverses_the_sign(self):
        difference = TemporaryDifference(
            "accrual", Money.of(30000, "USD"), Money.of(10000, "USD"),
            is_asset_side=False,
        )
        assert not difference.creates_liability()
        assert difference.taxable_amount() == Money.of("-20000.00", "USD")


class TestBalance:
    def test_the_balance_is_the_difference_at_the_rate(self):
        account = _account()
        account.add(_asset_difference())
        assert account.required_balance() == Money.of(10000, "USD")
        assert account.is_liability()

    def test_a_net_asset_position_is_named(self):
        account = _account()
        account.add(
            TemporaryDifference("provision", Money.of(10000, "USD"), Money.of(50000, "USD"))
        )
        assert account.is_asset()

    def test_the_movement_is_the_increment(self):
        account = _account()
        account.add(_asset_difference())
        assert account.post() == Money.of(10000, "USD")
        account.add(
            TemporaryDifference("more plant", Money.of(20000, "USD"), Money.zero("USD"))
        )
        assert account.movement() == Money.of(5000, "USD")

    def test_posting_twice_moves_nothing(self):
        account = _account()
        account.add(_asset_difference())
        account.post()
        assert account.post().is_zero()


class TestRemeasurement:
    def test_a_rate_change_restates_the_whole_balance(self):
        account = _account()
        account.add(_asset_difference())
        account.post()
        change = account.remeasure(Fraction(30, 100))
        assert change == Money.of(2000, "USD")
        assert account.required_balance() == Money.of(12000, "USD")

    def test_a_rate_cut_reduces_the_liability(self):
        account = _account()
        account.add(_asset_difference())
        assert account.remeasure(Fraction(20, 100)).is_negative()

    def test_an_invalid_rate_is_refused(self):
        with pytest.raises(Refused):
            _account().remeasure(Fraction(1))


class TestPermanent:
    def test_a_permanent_difference_never_touches_deferred_tax(self):
        item = PermanentDifference("entertaining", Money.of(5000, "USD"))
        assert not item.affects_deferred_tax()


class TestRefusals:
    def test_a_wrong_currency_difference_is_refused(self):
        with pytest.raises(Refused):
            _account().add(
                TemporaryDifference("x", Money.of(1, "EUR"), Money.zero("EUR"))
            )

    def test_a_rate_of_one_is_refused(self):
        with pytest.raises(Refused):
            _account(Fraction(1))
