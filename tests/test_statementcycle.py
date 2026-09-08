from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.statementcycle import (
    CardTerms,
    Statement,
    cost_of_minimum_only,
    months_to_clear,
)


def _terms(**kwargs) -> CardTerms:
    base = {
        "annual_rate": Fraction(24, 100),
        "minimum_floor": Money.of(25, "USD"),
        "minimum_rate": Fraction(2, 100),
    }
    base.update(kwargs)
    return CardTerms(**base)


def _statement(payments: str, opening: str = "1000.00") -> Statement:
    return Statement(
        opening=Money.of(opening, "USD"),
        purchases=Money.of(200, "USD"),
        payments=Money.of(payments, "USD"),
        terms=_terms(),
    )


class TestGracePeriod:
    def test_paying_in_full_charges_no_interest(self):
        statement = _statement("1000.00")
        assert statement.paid_in_full()
        assert statement.interest_charged().is_zero()

    def test_a_cent_short_loses_the_whole_grace(self):
        statement = _statement("999.99")
        assert not statement.paid_in_full()
        assert statement.interest_charged().is_positive()

    def test_the_cliff_is_not_a_slope(self):
        # A cent less paid does not mean a cent of interest; the whole
        # closing balance is charged.
        short = _statement("999.99")
        assert short.interest_charged() == Money.of("4.00", "USD")

    def test_paying_nothing_charges_on_the_closing_balance(self):
        statement = _statement("0.00")
        assert statement.closing() == Money.of(1200, "USD")
        assert statement.interest_charged() == Money.of(24, "USD")


class TestMinimumPayment:
    def test_the_floor_applies_to_a_small_balance(self):
        statement = Statement(
            opening=Money.of(100, "USD"),
            purchases=Money.zero("USD"),
            payments=Money.zero("USD"),
            terms=_terms(),
        )
        assert statement.minimum_payment() == Money.of(25, "USD")

    def test_the_percentage_applies_to_a_large_balance(self):
        statement = _statement("0.00")
        # 2% of 1200 is 24, below the 25 floor, so the floor wins.
        assert statement.minimum_payment() == Money.of(25, "USD")

    def test_a_very_large_balance_uses_the_percentage(self):
        statement = Statement(
            opening=Money.of(10000, "USD"),
            purchases=Money.zero("USD"),
            payments=Money.zero("USD"),
            terms=_terms(),
        )
        assert statement.minimum_payment() == Money.of(200, "USD")

    def test_the_minimum_never_exceeds_the_balance(self):
        statement = Statement(
            opening=Money.of(10, "USD"),
            purchases=Money.zero("USD"),
            payments=Money.zero("USD"),
            terms=_terms(),
        )
        assert statement.minimum_payment() == Money.of(10, "USD")

    def test_a_settled_card_owes_no_minimum(self):
        statement = _statement("1200.00")
        assert statement.minimum_payment().is_zero()


class TestMinimumOnly:
    def test_paying_the_minimum_takes_years(self):
        # A three percent minimum against a twenty-four percent APR does
        # clear, eventually.
        terms = _terms(minimum_rate=Fraction(3, 100))
        months = months_to_clear(Money.of(5000, "USD"), terms)
        assert months is not None
        assert months > 24

    def test_the_cost_of_paying_the_minimum_is_visible(self):
        terms = _terms(minimum_rate=Fraction(3, 100))
        cost = cost_of_minimum_only(Money.of(5000, "USD"), terms)
        assert cost is not None
        assert cost.is_positive()

    def test_a_two_percent_minimum_at_this_apr_never_clears(self):
        # Twenty-four percent a year is two percent a month, which is
        # exactly the two percent minimum, so the balance never moves.
        assert months_to_clear(Money.of(5000, "USD"), _terms()) is None

    def test_a_minimum_below_the_interest_never_clears(self):
        terms = _terms(annual_rate=Fraction(60, 100), minimum_rate=Fraction(1, 100),
                       minimum_floor=Money.zero("USD"))
        assert months_to_clear(Money.of(10000, "USD"), terms) is None

    def test_a_settled_balance_clears_at_once(self):
        assert months_to_clear(Money.zero("USD"), _terms()) == 0


class TestTerms:
    def test_a_negative_rate_is_refused(self):
        with pytest.raises(Refused):
            _terms(annual_rate=Fraction(-1, 100))

    def test_a_minimum_rate_of_one_is_refused(self):
        with pytest.raises(Refused):
            _terms(minimum_rate=Fraction(1))
