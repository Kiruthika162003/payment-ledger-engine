from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.tips import Gratuity, TipPool, Worker

DAY = datetime.date(2026, 7, 1)


def _pool() -> TipPool:
    pool = TipPool("USD")
    pool.record(Money.of(300, "USD"), DAY, Gratuity.TIP)
    pool.record(Money.of(200, "USD"), DAY, Gratuity.SERVICE_CHARGE)
    pool.add_worker(Worker("alice", Fraction(40)))
    pool.add_worker(Worker("bob", Fraction(20)))
    return pool


class TestClassification:
    def test_tips_belong_to_the_staff(self):
        pool = _pool()
        assert pool.tips_collected() == Money.of(300, "USD")

    def test_service_charges_are_the_employers_revenue(self):
        pool = _pool()
        assert pool.service_charge_revenue() == Money.of(200, "USD")

    def test_the_two_are_never_mixed(self):
        pool = _pool()
        assert pool.tips_collected() != pool.service_charge_revenue()
        assert pool.distributable() == Money.of(300, "USD")

    def test_a_receipt_knows_which_it_is(self):
        pool = _pool()
        assert pool.receipts[0].belongs_to_staff()
        assert pool.receipts[1].is_revenue()


class TestDistribution:
    def test_the_pool_splits_by_hours(self):
        pool = _pool()
        shares = dict(pool.distribution())
        assert shares["alice"] == Money.of(200, "USD")
        assert shares["bob"] == Money.of(100, "USD")

    def test_a_role_weight_changes_the_split(self):
        pool = _pool()
        pool.add_worker(Worker("chef", Fraction(40), role_weight=Fraction(1, 2)))
        shares = dict(pool.distribution())
        assert shares["chef"] < shares["alice"]

    def test_the_distribution_conserves_the_cent(self):
        pool = TipPool("USD")
        pool.record(Money.of("100.01", "USD"), DAY, Gratuity.TIP)
        for name in ("a", "b", "c"):
            pool.add_worker(Worker(name, Fraction(1)))
        assert pool.distribution_is_complete()

    def test_a_named_share_can_be_looked_up(self):
        assert _pool().share_for("alice") == Money.of(200, "USD")

    def test_an_unknown_worker_is_refused(self):
        with pytest.raises(Refused):
            _pool().share_for("nobody")

    def test_a_pool_with_no_workers_is_refused(self):
        pool = TipPool("USD")
        pool.record(Money.of(100, "USD"), DAY, Gratuity.TIP)
        with pytest.raises(Refused):
            pool.distribution()


class TestDeductions:
    def test_a_permitted_deduction_reduces_the_pool(self):
        pool = _pool()
        pool.deduct("card processing", Money.of(9, "USD"))
        assert pool.distributable() == Money.of(291, "USD")

    def test_an_unpermitted_deduction_is_refused(self):
        with pytest.raises(Refused) as caught:
            _pool().deduct("breakages", Money.of(50, "USD"))
        assert "belongs to the people who earned it" in str(caught.value)

    def test_a_deduction_beyond_the_pool_is_refused(self):
        with pytest.raises(Refused):
            _pool().deduct("card processing", Money.of(500, "USD"))

    def test_the_distribution_follows_the_deduction(self):
        pool = _pool()
        pool.deduct("card processing", Money.of(30, "USD"))
        assert pool.share_for("alice") == Money.of(180, "USD")


class TestRefusals:
    def test_a_duplicate_worker_is_refused(self):
        pool = _pool()
        with pytest.raises(Refused):
            pool.add_worker(Worker("alice", Fraction(10)))

    def test_a_worker_with_no_hours_is_refused(self):
        with pytest.raises(Refused):
            Worker("ghost", Fraction(0))

    def test_a_wrong_currency_receipt_is_refused(self):
        with pytest.raises(Refused):
            _pool().record(Money.of(10, "EUR"), DAY, Gratuity.TIP)

    def test_a_nonpositive_receipt_is_refused(self):
        with pytest.raises(Refused):
            _pool().record(Money.zero("USD"), DAY, Gratuity.TIP)
