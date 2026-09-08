from __future__ import annotations

import datetime
from fractions import Fraction

from mint.conversion import convert, convert_at, convert_exact, exact_minor
from mint.fxrate import RateTable
from mint.money import Money
from mint.rounding import Rounding

DAY = datetime.date(2026, 1, 1)


class TestConvertAt:
    def test_a_same_exponent_conversion(self):
        # 10.00 USD at 0.90 = 9.00 EUR.
        result = convert_at(Money.of(10, "USD"), "EUR", Fraction(9, 10))
        assert result == Money.of("9.00", "EUR")

    def test_dollars_to_yen_carry_the_exponent(self):
        # 10.00 USD at 150 yen per dollar = 1500 yen, not 150000.
        result = convert_at(Money.of(10, "USD"), "JPY", Fraction(150))
        assert result == Money.of("1500", "JPY")

    def test_yen_to_dollars_carry_the_exponent_back(self):
        # 1500 JPY at 1/150 dollars per yen = 10.00 USD.
        result = convert_at(Money.of("1500", "JPY"), "USD", Fraction(1, 150))
        assert result == Money.of("10.00", "USD")

    def test_the_same_currency_is_returned_untouched(self):
        money = Money.of(10, "USD")
        assert convert_at(money, "USD", Fraction(2)) is money


class TestRounding:
    def test_a_fractional_cent_rounds_half_even(self):
        # 1.00 USD at 1/3 = 33.33... cents rounds to 33.
        assert convert_at(Money.of(1, "USD"), "EUR", Fraction(1, 3)) == Money.from_minor(
            33, "EUR"
        )

    def test_the_mode_is_honored(self):
        up = convert_at(Money.of(1, "USD"), "EUR", Fraction(1, 3), Rounding.CEILING)
        assert up == Money.from_minor(34, "EUR")


class TestConvertThroughTable:
    def test_conversion_uses_the_table_rate(self):
        table = RateTable()
        table.add("USD", "EUR", Fraction(9, 10), DAY)
        assert convert(Money.of(10, "USD"), "EUR", table, DAY) == Money.of("9.00", "EUR")

    def test_the_exact_figure_skips_rounding(self):
        table = RateTable()
        table.add("USD", "EUR", Fraction(1, 3), DAY)
        assert convert_exact(Money.of(1, "USD"), "EUR", table, DAY) == Fraction(100, 3)

    def test_exact_minor_carries_the_exponent(self):
        assert exact_minor(Money.of(10, "USD"), "JPY", Fraction(150)) == Fraction(1500)
