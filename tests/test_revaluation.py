from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.revaluation import revalue


class TestAsset:
    def test_a_strengthened_foreign_asset_books_a_gain(self):
        # 100 EUR carried at 1.00/EUR = 100 USD; now 1.20/EUR = 120 USD.
        result = revalue(Money.of(100, "EUR"), Money.of(100, "USD"), Fraction(12, 10))
        assert result.revalued == Money.of(120, "USD")
        assert result.gain_loss == Money.of(20, "USD")
        assert result.is_gain()

    def test_a_weakened_foreign_asset_books_a_loss(self):
        result = revalue(Money.of(100, "EUR"), Money.of(100, "USD"), Fraction(9, 10))
        assert result.gain_loss == Money.of("-10.00", "USD")
        assert result.is_loss()


class TestLiability:
    def test_a_strengthened_foreign_liability_books_a_loss(self):
        # Owing 100 EUR: if EUR strengthens, we owe more in USD, a loss.
        result = revalue(
            Money.of(100, "EUR"), Money.of(100, "USD"), Fraction(12, 10), is_liability=True
        )
        assert result.is_loss()
        assert result.gain_loss == Money.of("-20.00", "USD")


class TestRefusals:
    def test_revaluing_the_same_currency_is_refused(self):
        with pytest.raises(Refused):
            revalue(Money.of(100, "USD"), Money.of(100, "USD"), Fraction(1))
