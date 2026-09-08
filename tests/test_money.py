from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import CurrencyMismatch, Refused
from mint.money import Money


class TestConstruction:
    def test_of_an_integer_is_whole_major_units(self):
        assert Money.of(10, "USD").units == 1000

    def test_of_a_decimal_string_is_exact(self):
        assert Money.of("10.50", "USD").units == 1050

    def test_a_short_fraction_pads_to_the_exponent(self):
        assert Money.of("10.5", "USD").units == 1050

    def test_yen_takes_no_decimals(self):
        assert Money.of("1000", "JPY").units == 1000

    def test_a_float_is_refused_at_the_door(self):
        with pytest.raises(Refused) as caught:
            Money.of(10.5, "USD")
        assert "float" in str(caught.value)

    def test_too_many_decimals_is_refused(self):
        with pytest.raises(Refused) as caught:
            Money.of("10.567", "USD")
        assert "minor units" in str(caught.value)

    def test_a_thousands_separator_is_refused(self):
        with pytest.raises(Refused):
            Money.of("1,000.00", "USD")

    def test_a_negative_string_parses(self):
        assert Money.of("-10.50", "USD").units == -1050


class TestArithmetic:
    def test_addition_is_exact(self):
        assert (Money.of("0.10", "USD") + Money.of("0.20", "USD")).units == 30

    def test_a_tenth_summed_ten_times_is_exactly_one(self):
        total = Money.zero("USD")
        for _ in range(10):
            total = total + Money.of("0.10", "USD")
        assert total == Money.of("1.00", "USD")

    def test_subtraction_can_go_negative(self):
        assert (Money.of(1, "USD") - Money.of(3, "USD")).units == -200

    def test_adding_across_currencies_is_a_category_error(self):
        with pytest.raises(CurrencyMismatch):
            Money.of(1, "USD") + Money.of(1, "EUR")

    def test_times_returns_an_exact_fraction(self):
        assert Money.of(1, "USD").times(Fraction(1, 3)) == Fraction(100, 3)


class TestComparison:
    def test_equality_across_currencies_is_false_not_an_error(self):
        assert Money.of(10, "USD") != Money.of(10, "EUR")

    def test_ordering_across_currencies_raises(self):
        with pytest.raises(CurrencyMismatch):
            _ = Money.of(1, "USD") < Money.of(1, "EUR")

    def test_ordering_within_a_currency_works(self):
        assert Money.of(1, "USD") < Money.of(2, "USD")


class TestFormatting:
    def test_dollars_show_two_places(self):
        assert Money.of("10.50", "USD").format() == "$10.50"

    def test_yen_shows_no_places(self):
        assert Money.of("1000", "JPY").format() == "¥1000"

    def test_negative_amounts_lead_with_the_sign(self):
        assert Money.of("-10.50", "USD").format() == "-$10.50"

    def test_code_form_omits_the_symbol(self):
        assert Money.of("10.50", "USD").format(with_symbol=False) == "10.50 USD"
