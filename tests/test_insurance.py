from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.insurance import ClaimHistory, Policy
from mint.money import Money


def _policy(**kwargs) -> Policy:
    base = {
        "deductible": Money.of(1000, "USD"),
        "coinsurance": Fraction(80, 100),
        "per_claim_limit": Money.of(50000, "USD"),
        "aggregate_limit": Money.of(100000, "USD"),
    }
    base.update(kwargs)
    return Policy(**base)


def _history(**kwargs) -> ClaimHistory:
    return ClaimHistory(policy=_policy(**kwargs), currency="USD")


class TestOrder:
    def test_the_deductible_comes_off_first(self):
        settlement = _history().settle(Money.of(11000, "USD"))
        assert settlement.after_deductible == Money.of(10000, "USD")

    def test_coinsurance_applies_above_the_deductible_not_to_the_whole_loss(self):
        settlement = _history().settle(Money.of(11000, "USD"))
        # Eighty percent of 10000, not of 11000.
        assert settlement.after_coinsurance == Money.of(8000, "USD")
        assert settlement.payable == Money.of(8000, "USD")

    def test_a_loss_below_the_deductible_pays_nothing(self):
        settlement = _history().settle(Money.of(500, "USD"))
        assert settlement.payable.is_zero()
        assert settlement.after_deductible.is_zero()

    def test_the_settlement_reconciles(self):
        settlement = _history().settle(Money.of(11000, "USD"))
        assert settlement.reconciles()
        assert settlement.insured_share() == Money.of(3000, "USD")


class TestLimits:
    def test_the_per_claim_limit_caps_a_large_loss(self):
        settlement = _history().settle(Money.of(200000, "USD"))
        assert settlement.payable == Money.of(50000, "USD")
        assert settlement.capped_by == "the per-claim limit"

    def test_an_uncapped_claim_says_so(self):
        settlement = _history().settle(Money.of(11000, "USD"))
        assert settlement.capped_by is None

    def test_the_aggregate_limit_caps_a_later_claim(self):
        history = _history()
        history.settle(Money.of(200000, "USD"))
        history.settle(Money.of(200000, "USD"))
        third = history.settle(Money.of(200000, "USD"))
        assert third.capped_by == "the aggregate limit for the year"
        assert history.is_exhausted()

    def test_the_aggregate_remaining_counts_down(self):
        history = _history()
        history.settle(Money.of(200000, "USD"))
        assert history.aggregate_remaining() == Money.of(50000, "USD")

    def test_an_exhausted_policy_pays_nothing_more(self):
        history = _history()
        history.settle(Money.of(200000, "USD"))
        history.settle(Money.of(200000, "USD"))
        assert history.settle(Money.of(50000, "USD")).payable.is_zero()


class TestHistory:
    def test_total_paid_accumulates(self):
        history = _history()
        history.settle(Money.of(11000, "USD"))
        history.settle(Money.of(6000, "USD"))
        assert history.total_paid() == Money.of(12000, "USD")

    def test_the_recovery_rate_is_below_one(self):
        history = _history()
        history.settle(Money.of(11000, "USD"))
        rate = history.recovery_rate()
        assert rate is not None
        assert rate < 1

    def test_no_recovery_rate_without_claims(self):
        assert _history().recovery_rate() is None

    def test_total_losses_are_tracked_apart_from_payments(self):
        history = _history()
        history.settle(Money.of(11000, "USD"))
        assert history.total_losses() == Money.of(11000, "USD")
        assert history.total_paid() < history.total_losses()


class TestConstruction:
    def test_a_zero_coinsurance_is_refused(self):
        with pytest.raises(Refused):
            _policy(coinsurance=Fraction(0))

    def test_a_negative_deductible_is_refused(self):
        with pytest.raises(Refused):
            _policy(deductible=Money.of("-1.00", "USD"))

    def test_an_aggregate_below_the_per_claim_limit_is_refused(self):
        with pytest.raises(Refused) as caught:
            _policy(aggregate_limit=Money.of(1000, "USD"))
        assert "never be reached" in str(caught.value)

    def test_a_wrong_currency_claim_is_refused(self):
        with pytest.raises(Refused):
            _history().settle(Money.of(1000, "EUR"))

    def test_a_nonpositive_claim_is_refused(self):
        with pytest.raises(Refused):
            _history().settle(Money.zero("USD"))
