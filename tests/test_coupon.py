from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.coupon import Coupon, apply_coupons
from mint.errors import Refused
from mint.money import Money

DAY = datetime.date(2026, 5, 1)
LATER = datetime.date(2026, 7, 1)


def _coupon(**kwargs) -> Coupon:
    base = {"code": "SAVE10", "percent_off": Fraction(10, 100)}
    base.update(kwargs)
    return Coupon(**base)


class TestDiscount:
    def test_a_percentage_coupon(self):
        assert _coupon().discount_on(Money.of(100, "USD")) == Money.of(10, "USD")

    def test_a_fixed_coupon(self):
        coupon = Coupon(code="TEN", amount_off=Money.of(10, "USD"))
        assert coupon.discount_on(Money.of(100, "USD")) == Money.of(10, "USD")

    def test_a_discount_never_exceeds_the_order(self):
        coupon = Coupon(code="BIG", amount_off=Money.of(500, "USD"))
        assert coupon.discount_on(Money.of(100, "USD")) == Money.of(100, "USD")

    def test_a_coupon_that_takes_nothing_off_is_refused(self):
        with pytest.raises(Refused):
            Coupon(code="NOTHING")


class TestLimits:
    def test_a_total_cap_is_enforced(self):
        coupon = _coupon(total_limit=2)
        coupon.redeem("a", Money.of(100, "USD"), DAY)
        coupon.redeem("b", Money.of(100, "USD"), DAY)
        with pytest.raises(Refused) as caught:
            coupon.redeem("c", Money.of(100, "USD"), DAY)
        assert "redemption limit" in str(caught.value)

    def test_a_per_customer_cap_is_enforced(self):
        coupon = _coupon(per_customer_limit=1)
        coupon.redeem("a", Money.of(100, "USD"), DAY)
        with pytest.raises(Refused) as caught:
            coupon.redeem("a", Money.of(100, "USD"), DAY)
        assert "maximum number" in str(caught.value)

    def test_another_customer_is_unaffected(self):
        coupon = _coupon(per_customer_limit=1)
        coupon.redeem("a", Money.of(100, "USD"), DAY)
        assert coupon.redeem("b", Money.of(100, "USD"), DAY).customer_id == "b"

    def test_a_minimum_order_blocks_a_small_basket(self):
        coupon = _coupon(minimum_order=Money.of(50, "USD"))
        blocked = coupon.blocked_reason("a", Money.of(20, "USD"), DAY)
        assert "below the" in blocked

    def test_an_expired_coupon_is_blocked(self):
        coupon = _coupon(expires=DAY)
        assert "expired" in coupon.blocked_reason("a", Money.of(100, "USD"), LATER)

    def test_a_coupon_not_yet_started_is_blocked(self):
        coupon = _coupon(starts=LATER)
        assert "not valid until" in coupon.blocked_reason("a", Money.of(100, "USD"), DAY)

    def test_the_reason_tells_the_customer_what_to_do(self):
        coupon = _coupon(minimum_order=Money.of(50, "USD"))
        reason = coupon.blocked_reason("a", Money.of(20, "USD"), DAY)
        assert "minimum" in reason


class TestTracking:
    def test_remaining_counts_down(self):
        coupon = _coupon(total_limit=3)
        coupon.redeem("a", Money.of(100, "USD"), DAY)
        assert coupon.remaining() == 2

    def test_an_uncapped_coupon_has_no_remaining_count(self):
        assert _coupon().remaining() is None

    def test_exhaustion_is_reported(self):
        coupon = _coupon(total_limit=1)
        coupon.redeem("a", Money.of(100, "USD"), DAY)
        assert coupon.is_exhausted()

    def test_the_total_discount_given_is_tracked(self):
        coupon = _coupon()
        coupon.redeem("a", Money.of(100, "USD"), DAY)
        coupon.redeem("b", Money.of(200, "USD"), DAY)
        assert coupon.total_discount_given("USD") == Money.of(30, "USD")


class TestStacking:
    def test_two_combinable_coupons_stack(self):
        first = _coupon(code="A", combinable=True)
        second = Coupon(code="B", amount_off=Money.of(5, "USD"), combinable=True)
        final, applied = apply_coupons(
            Money.of(100, "USD"), [first, second], "a", DAY
        )
        assert final == Money.of(85, "USD")
        assert applied == ["A", "B"]

    def test_a_non_combinable_coupon_blocks_stacking(self):
        first = _coupon(code="A", combinable=False)
        second = Coupon(code="B", amount_off=Money.of(5, "USD"), combinable=True)
        with pytest.raises(Refused) as caught:
            apply_coupons(Money.of(100, "USD"), [first, second], "a", DAY)
        assert "cannot be combined" in str(caught.value)

    def test_a_single_coupon_applies_regardless(self):
        final, _applied = apply_coupons(Money.of(100, "USD"), [_coupon()], "a", DAY)
        assert final == Money.of(90, "USD")

    def test_stacked_discounts_never_go_below_zero(self):
        first = Coupon(code="A", amount_off=Money.of(80, "USD"), combinable=True)
        second = Coupon(code="B", amount_off=Money.of(80, "USD"), combinable=True)
        final, _applied = apply_coupons(
            Money.of(100, "USD"), [first, second], "a", DAY
        )
        assert final.is_zero()
