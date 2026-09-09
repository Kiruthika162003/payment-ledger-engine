from __future__ import annotations

from fractions import Fraction

import pytest

from mint.bonuspool import BonusPool, Participant
from mint.errors import Refused
from mint.money import Money


def _pool(**kwargs) -> BonusPool:
    base = {
        "currency": "USD",
        "target_pool": Money.of(100000, "USD"),
        "maximum_pool": Money.of(150000, "USD"),
    }
    base.update(kwargs)
    pool = BonusPool(**base)
    pool.add(Participant("alice", Fraction(3)))
    pool.add(Participant("bob", Fraction(2)))
    pool.add(Participant("carol", Fraction(1)))
    return pool


class TestEarnedPool:
    def test_on_target_earns_the_target_pool(self):
        assert _pool().earned_pool(Fraction(1)) == Money.of(100000, "USD")

    def test_under_target_earns_less(self):
        assert _pool().earned_pool(Fraction(80, 100)) == Money.of(80000, "USD")

    def test_over_target_is_capped_at_the_maximum(self):
        pool = _pool()
        assert pool.earned_pool(Fraction(2)) == Money.of(150000, "USD")
        assert pool.is_capped(Fraction(2))

    def test_negative_achievement_is_refused(self):
        with pytest.raises(Refused):
            _pool().earned_pool(Fraction(-1))


class TestAccrual:
    def test_accrual_scales_with_the_year_elapsed(self):
        pool = _pool()
        assert pool.required_accrual(Fraction(1), Fraction(1, 2)) == Money.of(
            50000, "USD"
        )

    def test_posting_accrues_the_increment(self):
        pool = _pool()
        assert pool.post(Fraction(1), Fraction(1, 4)) == Money.of(25000, "USD")
        assert pool.post(Fraction(1), Fraction(1, 2)) == Money.of(25000, "USD")

    def test_a_late_collapse_produces_a_credit(self):
        pool = _pool()
        pool.post(Fraction(1), Fraction(3, 4))
        movement = pool.post(Fraction(1, 4), Fraction(1))
        assert movement.is_negative()
        assert pool.accrued == Money.of(25000, "USD")

    def test_settling_trues_up_to_the_final_pool(self):
        pool = _pool()
        pool.post(Fraction(1), Fraction(3, 4))
        assert pool.settle(Fraction(1)) == Money.of(25000, "USD")
        assert pool.accrued == Money.of(100000, "USD")

    def test_an_impossible_year_fraction_is_refused(self):
        with pytest.raises(Refused):
            _pool().required_accrual(Fraction(1), Fraction(2))


class TestShares:
    def test_shares_follow_the_weights(self):
        shares = dict(_pool().shares(Fraction(1)))
        assert shares["alice"] == Money.of(50000, "USD")
        assert shares["bob"] == Money.from_minor(3333333, "USD")

    def test_the_shares_fund_the_pool_exactly(self):
        assert _pool().shares_fund_the_pool(Fraction(1))

    def test_an_awkward_pool_still_funds_exactly(self):
        pool = _pool(
            target_pool=Money.of("100000.07", "USD"),
            maximum_pool=Money.of("200000.00", "USD"),
        )
        assert pool.shares_fund_the_pool(Fraction(1))

    def test_a_capped_pool_shares_the_cap(self):
        pool = _pool()
        total = Money.zero("USD")
        for _, amount in pool.shares(Fraction(2)):
            total = total + amount
        assert total == Money.of(150000, "USD")

    def test_an_empty_pool_funds_nothing(self):
        pool = BonusPool(
            currency="USD",
            target_pool=Money.of(1000, "USD"),
            maximum_pool=Money.of(2000, "USD"),
        )
        with pytest.raises(Refused):
            pool.shares(Fraction(1))


class TestConstruction:
    def test_a_maximum_below_the_target_is_refused(self):
        with pytest.raises(Refused) as caught:
            _pool(maximum_pool=Money.of(1000, "USD"))
        assert "never be reached" in str(caught.value)

    def test_a_duplicate_participant_is_refused(self):
        pool = _pool()
        with pytest.raises(Refused):
            pool.add(Participant("alice", Fraction(1)))

    def test_a_nonpositive_weight_is_refused(self):
        with pytest.raises(Refused):
            Participant("dave", Fraction(0))
