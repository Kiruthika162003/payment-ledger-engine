from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.taxbracket import Bracket, BracketTable


def _table() -> BracketTable:
    return BracketTable(
        brackets=(
            Bracket(Money.zero("USD"), Fraction(10, 100)),
            Bracket(Money.of(10000, "USD"), Fraction(20, 100)),
            Bracket(Money.of(40000, "USD"), Fraction(30, 100)),
        )
    )


class TestSlices:
    def test_only_the_slice_is_taxed_at_the_higher_rate(self):
        # 10000 at 10% = 1000, then 5000 at 20% = 1000, total 2000.
        result = _table().tax_on(Money.of(15000, "USD"))
        assert result.tax == Money.of(2000, "USD")

    def test_income_inside_the_first_bracket(self):
        assert _table().tax_on(Money.of(5000, "USD")).tax == Money.of(500, "USD")

    def test_the_slices_are_reported(self):
        result = _table().tax_on(Money.of(15000, "USD"))
        assert [label for label, _ in result.slices] == ["10%", "20%"]

    def test_zero_income_is_taxed_nothing(self):
        assert _table().tax_on(Money.zero("USD")).tax.is_zero()


class TestRates:
    def test_the_marginal_rate_is_the_rate_on_the_next_dollar(self):
        assert _table().marginal_rate(Money.of(15000, "USD")) == Fraction(20, 100)

    def test_the_effective_rate_is_lower_than_the_marginal(self):
        result = _table().tax_on(Money.of(15000, "USD"))
        assert result.effective_rate() < _table().marginal_rate(Money.of(15000, "USD"))

    def test_no_effective_rate_on_no_income(self):
        assert _table().tax_on(Money.zero("USD")).effective_rate() is None


class TestTheMisconception:
    def test_a_raise_never_reduces_take_home(self):
        table = _table()
        for gross in range(9000, 41000, 500):
            before = Money.of(gross, "USD")
            after = Money.of(gross + 500, "USD")
            assert table.raise_is_never_a_loss(before, after)

    def test_crossing_a_bracket_still_leaves_more(self):
        table = _table()
        assert table.take_home(Money.of(10500, "USD")) > table.take_home(
            Money.of(9900, "USD")
        )


class TestConstruction:
    def test_the_first_bracket_starts_at_zero(self):
        with pytest.raises(Refused):
            BracketTable(brackets=(Bracket(Money.of(100, "USD"), Fraction(1, 10)),))

    def test_floors_must_increase(self):
        with pytest.raises(Refused):
            BracketTable(
                brackets=(
                    Bracket(Money.zero("USD"), Fraction(1, 10)),
                    Bracket(Money.of(40000, "USD"), Fraction(2, 10)),
                    Bracket(Money.of(10000, "USD"), Fraction(3, 10)),
                )
            )

    def test_a_rate_of_one_is_refused(self):
        with pytest.raises(Refused):
            Bracket(Money.zero("USD"), Fraction(1))

    def test_negative_income_is_refused(self):
        with pytest.raises(Refused):
            _table().tax_on(Money.of("-100.00", "USD"))
