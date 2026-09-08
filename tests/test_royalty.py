from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.royalty import RoyaltyContract


def _contract(**kwargs) -> RoyaltyContract:
    base = {
        "creator": "author",
        "currency": "USD",
        "rate": Fraction(10, 100),
        "advance": Money.of(5000, "USD"),
    }
    base.update(kwargs)
    return RoyaltyContract(**base)


class TestRecoupment:
    def test_early_royalties_pay_down_the_advance(self):
        contract = _contract()
        period = contract.record("Q1", Money.of(20000, "USD"))
        assert period.earned == Money.of(2000, "USD")
        assert period.recouped == Money.of(2000, "USD")
        assert period.payable.is_zero()
        assert period.unearned_after == Money.of(3000, "USD")

    def test_nothing_is_payable_until_the_advance_is_earned_back(self):
        contract = _contract()
        contract.record("Q1", Money.of(20000, "USD"))
        contract.record("Q2", Money.of(20000, "USD"))
        assert contract.total_paid().is_zero()
        assert contract.unearned == Money.of(1000, "USD")

    def test_the_period_that_crosses_pays_the_excess(self):
        contract = _contract()
        contract.record("Q1", Money.of(40000, "USD"))
        period = contract.record("Q2", Money.of(30000, "USD"))
        # 3000 earned, 1000 recoups the rest of the advance, 2000 payable.
        assert period.recouped == Money.of(1000, "USD")
        assert period.payable == Money.of(2000, "USD")
        assert contract.is_recouped()

    def test_later_periods_pay_in_full(self):
        contract = _contract()
        contract.record("Q1", Money.of(60000, "USD"))
        period = contract.record("Q2", Money.of(10000, "USD"))
        assert period.payable == Money.of(1000, "USD")
        assert period.recouped.is_zero()


class TestGuarantee:
    def test_a_guarantee_tops_up_a_weak_period(self):
        contract = _contract(
            advance=Money.zero("USD"), minimum_guarantee=Money.of(500, "USD")
        )
        period = contract.record("Q1", Money.of(1000, "USD"))
        assert period.earned == Money.of(100, "USD")
        assert period.payable == Money.of(500, "USD")

    def test_a_strong_period_exceeds_the_guarantee(self):
        contract = _contract(
            advance=Money.zero("USD"), minimum_guarantee=Money.of(500, "USD")
        )
        period = contract.record("Q1", Money.of(20000, "USD"))
        assert period.payable == Money.of(2000, "USD")

    def test_a_guarantee_does_not_reduce_the_advance_further(self):
        contract = _contract(minimum_guarantee=Money.of(500, "USD"))
        contract.record("Q1", Money.of(1000, "USD"))
        assert contract.unearned == Money.of(4900, "USD")


class TestTotals:
    def test_everything_earned_is_recouped_or_paid(self):
        contract = _contract()
        contract.record("Q1", Money.of(40000, "USD"))
        contract.record("Q2", Money.of(30000, "USD"))
        assert contract.reconciles()

    def test_the_advance_is_never_clawed_back(self):
        contract = _contract()
        contract.record("Q1", Money.of(100, "USD"))
        assert not contract.unearned.is_negative()

    def test_publisher_outlay_counts_the_advance_and_the_payments(self):
        contract = _contract()
        contract.record("Q1", Money.of(60000, "USD"))
        assert contract.publisher_outlay() == Money.of(6000, "USD")


class TestRefusals:
    def test_a_rate_of_one_is_refused(self):
        with pytest.raises(Refused):
            _contract(rate=Fraction(1))

    def test_a_negative_advance_is_refused(self):
        with pytest.raises(Refused):
            _contract(advance=Money.of("-1.00", "USD"))

    def test_negative_sales_are_refused(self):
        with pytest.raises(Refused):
            _contract().record("Q1", Money.of("-1.00", "USD"))

    def test_a_wrong_currency_period_is_refused(self):
        with pytest.raises(Refused):
            _contract().record("Q1", Money.of(100, "EUR"))
