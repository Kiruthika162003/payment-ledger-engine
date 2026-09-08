from __future__ import annotations

from fractions import Fraction

import pytest

from mint.amortization import schedule
from mint.errors import Refused
from mint.money import Money


class TestInterestFree:
    def test_an_interest_free_loan_splits_evenly(self):
        result = schedule(Money.of(1200, "USD"), Fraction(0), 12, 12)
        assert all(row.interest == 0 for row in result.rows)
        assert result.total_paid() == Money.of(1200, "USD")
        assert result.final_balance() == 0


class TestLevelPayment:
    def test_the_balance_ends_exactly_at_zero(self):
        result = schedule(Money.of(1000, "USD"), Fraction(12, 100), 12, 12)
        assert result.final_balance() == 0

    def test_each_row_ties_payment_to_interest_plus_principal(self):
        result = schedule(Money.of(1000, "USD"), Fraction(12, 100), 12, 12)
        for row in result.rows:
            assert row.payment == row.interest + row.principal

    def test_the_first_payment_is_mostly_interest_at_a_high_rate(self):
        result = schedule(Money.of(1000, "USD"), Fraction(12, 100), 12, 12)
        first = result.rows[0]
        assert first.interest == 1000  # 1% of 1000.00 in cents

    def test_total_interest_is_total_paid_less_principal(self):
        result = schedule(Money.of(1000, "USD"), Fraction(12, 100), 12, 12)
        assert result.total_interest() == result.total_paid() - Money.of(1000, "USD")

    def test_principal_repaid_sums_to_the_loan(self):
        result = schedule(Money.of(1000, "USD"), Fraction(12, 100), 12, 12)
        assert sum(row.principal for row in result.rows) == 100000


class TestRefusals:
    def test_zero_periods_is_refused(self):
        with pytest.raises(Refused):
            schedule(Money.of(1000, "USD"), Fraction(1, 10), 0, 12)

    def test_a_negative_rate_is_refused(self):
        with pytest.raises(Refused):
            schedule(Money.of(1000, "USD"), Fraction(-1, 10), 12, 12)
