from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.bond import Bond
from mint.daycount import DayCount
from mint.errors import Refused
from mint.money import Money


def _bond(**kwargs) -> Bond:
    base = {
        "face": Money.of(1000, "USD"),
        "coupon_rate": Fraction(6, 100),
        "periods": 10,
        "coupons_per_year": 2,
    }
    base.update(kwargs)
    return Bond(**base)


class TestCoupons:
    def test_the_coupon_is_the_periodic_rate_on_face(self):
        assert _bond().coupon_payment() == Money.of(30, "USD")

    def test_total_coupons_over_the_life(self):
        assert _bond().total_coupons() == Money.of(300, "USD")


class TestPricing:
    def test_yield_equal_to_coupon_prices_at_par(self):
        bond = _bond()
        assert bond.prices_at_par(Fraction(6, 100))
        assert bond.price(Fraction(6, 100)) == Money.of(1000, "USD")

    def test_a_higher_yield_prices_at_a_discount(self):
        bond = _bond()
        assert bond.price(Fraction(8, 100)) < bond.face

    def test_a_lower_yield_prices_at_a_premium(self):
        bond = _bond()
        assert bond.price(Fraction(4, 100)) > bond.face

    def test_a_zero_yield_prices_at_face_plus_all_coupons(self):
        bond = _bond()
        assert bond.price(Fraction(0)) == Money.of(1300, "USD")

    def test_a_zero_coupon_bond_prices_below_face(self):
        bond = _bond(coupon_rate=Fraction(0))
        assert bond.price(Fraction(6, 100)) < bond.face


class TestAccrual:
    def test_half_a_period_accrues_half_a_coupon(self):
        bond = _bond(convention=DayCount.THIRTY_360)
        accrued = bond.accrued_interest(
            datetime.date(2026, 1, 1), datetime.date(2026, 4, 1)
        )
        # Three months of a 6% annual coupon on 1000 is 15.00.
        assert accrued == Money.of(15, "USD")

    def test_no_days_accrue_nothing(self):
        bond = _bond()
        same = datetime.date(2026, 1, 1)
        assert bond.accrued_interest(same, same).is_zero()

    def test_the_dirty_price_adds_the_accrual(self):
        bond = _bond(convention=DayCount.THIRTY_360)
        clean = bond.price(Fraction(6, 100))
        dirty = bond.dirty_price(
            Fraction(6, 100), datetime.date(2026, 1, 1), datetime.date(2026, 4, 1)
        )
        assert dirty - clean == Money.of(15, "USD")

    def test_settlement_before_the_coupon_is_refused(self):
        with pytest.raises(Refused):
            _bond().accrued_interest(
                datetime.date(2026, 4, 1), datetime.date(2026, 1, 1)
            )


class TestConstruction:
    def test_a_nonpositive_face_is_refused(self):
        with pytest.raises(Refused):
            _bond(face=Money.zero("USD"))

    def test_zero_periods_is_refused(self):
        with pytest.raises(Refused):
            _bond(periods=0)

    def test_a_negative_yield_is_refused(self):
        with pytest.raises(Refused):
            _bond().price(Fraction(-1, 100))
