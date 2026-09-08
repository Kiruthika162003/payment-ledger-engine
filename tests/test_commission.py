from __future__ import annotations

from fractions import Fraction

import pytest

from mint.commission import (
    AttainmentTier,
    CommissionBasis,
    CommissionLedger,
    CommissionPlan,
    split_commission,
)
from mint.errors import Refused
from mint.money import Money


def _plan(basis: CommissionBasis = CommissionBasis.ON_BOOKING) -> CommissionPlan:
    return CommissionPlan(
        currency="USD",
        tiers=(
            AttainmentTier(Money.zero("USD"), Fraction(5, 100)),
            AttainmentTier(Money.of(100000, "USD"), Fraction(10, 100)),
        ),
        basis=basis,
    )


class TestGraduatedRates:
    def test_below_quota_pays_the_base_rate(self):
        assert _plan().commission_on(Money.of(50000, "USD")) == Money.of(2500, "USD")

    def test_above_quota_the_excess_pays_more(self):
        # 100000 at 5% = 5000, then 50000 at 10% = 5000.
        assert _plan().commission_on(Money.of(150000, "USD")) == Money.of(10000, "USD")

    def test_zero_attainment_earns_nothing(self):
        assert _plan().commission_on(Money.zero("USD")).is_zero()

    def test_the_total_does_not_depend_on_deal_order(self):
        first = CommissionLedger(_plan())
        first.book("a", Money.of(120000, "USD"))
        first.book("b", Money.of(30000, "USD"))
        second = CommissionLedger(_plan())
        second.book("b", Money.of(30000, "USD"))
        second.book("a", Money.of(120000, "USD"))
        assert first.earned() == second.earned()


class TestBasis:
    def test_booking_basis_counts_bookings(self):
        ledger = CommissionLedger(_plan(CommissionBasis.ON_BOOKING))
        ledger.book("a", Money.of(50000, "USD"))
        assert ledger.attainment() == Money.of(50000, "USD")

    def test_collection_basis_waits_for_the_cash(self):
        ledger = CommissionLedger(_plan(CommissionBasis.ON_COLLECTION))
        ledger.book("a", Money.of(50000, "USD"))
        assert ledger.attainment().is_zero()
        ledger.collect(Money.of(20000, "USD"))
        assert ledger.attainment() == Money.of(20000, "USD")


class TestClawback:
    def test_a_refund_reduces_attainment(self):
        ledger = CommissionLedger(_plan())
        ledger.book("a", Money.of(50000, "USD"))
        ledger.refund(Money.of(10000, "USD"))
        assert ledger.attainment() == Money.of(40000, "USD")
        assert ledger.earned() == Money.of(2000, "USD")

    def test_paying_then_refunding_leaves_a_negative_payable(self):
        ledger = CommissionLedger(_plan())
        ledger.book("a", Money.of(50000, "USD"))
        ledger.pay()
        ledger.refund(Money.of(20000, "USD"))
        assert ledger.payable() == Money.of("-1000.00", "USD")

    def test_paying_settles_the_payable(self):
        ledger = CommissionLedger(_plan())
        ledger.book("a", Money.of(50000, "USD"))
        assert ledger.pay() == Money.of(2500, "USD")
        assert ledger.payable().is_zero()


class TestSplits:
    def test_a_split_conserves_the_cent(self):
        parts = split_commission(Money.of(100, "USD"), [1, 1, 1])
        assert [p.units for p in parts] == [3334, 3333, 3333]
        assert sum(p.units for p in parts) == 10000

    def test_weighted_splits_follow_the_weights(self):
        parts = split_commission(Money.of(100, "USD"), [3, 1])
        assert [p.units for p in parts] == [7500, 2500]

    def test_an_empty_split_is_refused(self):
        with pytest.raises(Refused):
            split_commission(Money.of(100, "USD"), [])


class TestConstruction:
    def test_the_first_tier_starts_at_zero(self):
        with pytest.raises(Refused):
            CommissionPlan(
                currency="USD",
                tiers=(AttainmentTier(Money.of(100, "USD"), Fraction(5, 100)),),
            )

    def test_a_wrong_currency_booking_is_refused(self):
        with pytest.raises(Refused):
            CommissionLedger(_plan()).book("a", Money.of(100, "EUR"))
