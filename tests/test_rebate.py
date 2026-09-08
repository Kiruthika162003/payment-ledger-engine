from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.rebate import RebateAgreement, RebateTier


def _agreement() -> RebateAgreement:
    return RebateAgreement(
        customer_id="c1",
        currency="USD",
        tiers=(
            RebateTier(Money.of(10000, "USD"), Fraction(2, 100)),
            RebateTier(Money.of(50000, "USD"), Fraction(5, 100)),
        ),
    )


class TestEarning:
    def test_nothing_is_earned_below_the_first_threshold(self):
        agreement = _agreement()
        agreement.buy(Money.of(5000, "USD"))
        assert agreement.earned().is_zero()

    def test_reaching_a_tier_applies_it_to_everything(self):
        agreement = _agreement()
        agreement.buy(Money.of(20000, "USD"))
        assert agreement.earned() == Money.of(400, "USD")

    def test_the_rate_jumps_at_the_next_threshold(self):
        agreement = _agreement()
        agreement.buy(Money.of(60000, "USD"))
        assert agreement.current_rate() == Fraction(5, 100)
        assert agreement.earned() == Money.of(3000, "USD")


class TestAccrual:
    def test_the_accrual_is_the_increment(self):
        agreement = _agreement()
        agreement.buy(Money.of(20000, "USD"))
        assert agreement.post_accrual() == Money.of(400, "USD")
        agreement.buy(Money.of(10000, "USD"))
        assert agreement.accrual_needed() == Money.of(200, "USD")

    def test_posting_twice_without_purchases_accrues_nothing(self):
        agreement = _agreement()
        agreement.buy(Money.of(20000, "USD"))
        agreement.post_accrual()
        assert agreement.post_accrual().is_zero()

    def test_crossing_a_threshold_produces_a_jump(self):
        agreement = _agreement()
        agreement.buy(Money.of(49000, "USD"))
        agreement.post_accrual()
        agreement.buy(Money.of(2000, "USD"))
        # Now at 51000 and 5%: 2550 earned, 980 already accrued.
        assert agreement.accrual_needed() == Money.of(1570, "USD")


class TestProgress:
    def test_the_next_threshold_is_reported(self):
        agreement = _agreement()
        agreement.buy(Money.of(20000, "USD"))
        assert agreement.next_threshold() == Money.of(50000, "USD")
        assert agreement.to_next_threshold() == Money.of(30000, "USD")

    def test_the_top_tier_has_no_next(self):
        agreement = _agreement()
        agreement.buy(Money.of(60000, "USD"))
        assert agreement.next_threshold() is None
        assert agreement.to_next_threshold() is None


class TestRefusals:
    def test_out_of_order_tiers_are_refused(self):
        with pytest.raises(Refused):
            RebateAgreement(
                customer_id="c1",
                currency="USD",
                tiers=(
                    RebateTier(Money.of(50000, "USD"), Fraction(5, 100)),
                    RebateTier(Money.of(10000, "USD"), Fraction(2, 100)),
                ),
            )

    def test_a_rate_of_one_is_refused(self):
        with pytest.raises(Refused):
            RebateTier(Money.of(100, "USD"), Fraction(1))

    def test_a_wrong_currency_purchase_is_refused(self):
        with pytest.raises(Refused):
            _agreement().buy(Money.of(100, "EUR"))
