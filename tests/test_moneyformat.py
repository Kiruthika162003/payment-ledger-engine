from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.moneyformat import (
    ACCOUNTING,
    EUROPEAN,
    PLAIN,
    US,
    Format,
    format_money,
    parse_money,
    round_trips,
)


class TestFormatting:
    def test_the_us_convention(self):
        assert format_money(Money.of("1234.56", "USD"), US) == "$1,234.56"

    def test_the_european_convention(self):
        assert format_money(Money.of("1234.56", "EUR"), EUROPEAN) == "1.234,56 €"

    def test_grouping_reaches_millions(self):
        assert format_money(Money.of("1234567.89", "USD"), US) == "$1,234,567.89"

    def test_a_currency_without_minor_units(self):
        assert format_money(Money.of("1000", "JPY"), US) == "¥1,000"

    def test_plain_drops_the_symbol_and_grouping(self):
        assert format_money(Money.of("1234.56", "USD"), PLAIN) == "1234.56"


class TestNegatives:
    def test_a_minus_by_default(self):
        assert format_money(Money.of("-5.00", "USD"), US) == "-$5.00"

    def test_parentheses_in_accounting_style(self):
        assert format_money(Money.of("-5.00", "USD"), ACCOUNTING) == "($5.00)"

    def test_a_positive_is_unbracketed(self):
        assert format_money(Money.of("5.00", "USD"), ACCOUNTING) == "$5.00"


class TestParsing:
    def test_parsing_inverts_formatting(self):
        for style in (US, EUROPEAN, ACCOUNTING, PLAIN):
            for text in ("1234.56", "-0.07", "0.00", "999999.99"):
                amount = Money.of(text, "USD")
                assert round_trips(amount, style)

    def test_a_european_figure_parses_back(self):
        assert parse_money("1.234,56 €", "EUR", EUROPEAN) == Money.of("1234.56", "EUR")

    def test_accounting_parentheses_parse_as_negative(self):
        assert parse_money("($5.00)", "USD", ACCOUNTING) == Money.of("-5.00", "USD")

    def test_an_unreadable_figure_is_refused(self):
        with pytest.raises(Refused) as caught:
            parse_money("twelve dollars", "USD", US)
        assert "misread by a thousand" in str(caught.value)

    def test_a_decimal_on_a_zero_exponent_currency_is_refused(self):
        with pytest.raises(Refused):
            parse_money("1.5", "JPY", US)

    def test_too_many_decimals_are_refused(self):
        with pytest.raises(Refused):
            parse_money("1.234", "USD", US)


class TestFormatConstruction:
    def test_identical_separators_are_refused(self):
        with pytest.raises(Refused) as caught:
            Format(group_separator=".", decimal_separator=".")
        assert "cannot be read back" in str(caught.value)

    def test_a_digit_separator_is_refused(self):
        with pytest.raises(Refused):
            Format(group_separator="0")
