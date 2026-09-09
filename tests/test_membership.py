from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.membership import Membership, MemberState
from mint.money import Money

YEAR_START = datetime.date(2026, 1, 1)
YEAR_END = datetime.date(2027, 1, 1)
JOINED = datetime.date(2026, 10, 1)
MID = datetime.date(2026, 11, 1)
AFTER = datetime.date(2027, 3, 1)


def _membership(**kwargs) -> Membership:
    base = {
        "id": "M-1",
        "member": "alice",
        "joining_fee": Money.of(50, "USD"),
        "annual_dues": Money.of(120, "USD"),
        "joined_on": JOINED,
        "year_start": YEAR_START,
        "year_end": YEAR_END,
    }
    base.update(kwargs)
    return Membership(**base)


class TestProration:
    def test_a_late_joiner_pays_for_the_rest_of_the_year(self):
        membership = _membership()
        assert membership.prorated_dues() < membership.annual_dues

    def test_the_joining_fee_is_charged_in_full(self):
        membership = _membership()
        due = membership.amount_due_on_joining()
        assert due == membership.joining_fee + membership.prorated_dues()

    def test_a_member_joining_on_day_one_pays_the_full_dues(self):
        membership = _membership(joined_on=YEAR_START)
        assert membership.prorated_dues() == Money.of(120, "USD")

    def test_joining_outside_the_year_is_refused(self):
        with pytest.raises(Refused):
            _membership(joined_on=datetime.date(2025, 1, 1))


class TestEarning:
    def test_the_joining_fee_is_earned_at_once(self):
        membership = _membership()
        assert membership.joining_fee_earned() == Money.of(50, "USD")

    def test_dues_are_earned_across_the_remaining_year(self):
        membership = _membership()
        assert membership.dues_earned_to(JOINED).is_zero()
        assert membership.dues_earned_to(MID).is_positive()
        assert membership.dues_earned_to(YEAR_END) == membership.prorated_dues()

    def test_the_unearned_part_is_the_complement(self):
        membership = _membership()
        earned = membership.dues_earned_to(MID)
        unearned = membership.unearned_dues_at(MID)
        assert earned + unearned == membership.prorated_dues()


class TestResignation:
    def test_the_refund_is_the_unearned_dues_only(self):
        membership = _membership()
        refund = membership.refund_on_resignation(MID)
        assert refund == membership.unearned_dues_at(MID)
        assert refund < membership.prorated_dues()

    def test_the_joining_fee_is_not_refunded(self):
        membership = _membership()
        refund = membership.resign(MID)
        assert refund < membership.joining_fee + membership.prorated_dues()

    def test_resigning_twice_is_refused(self):
        membership = _membership()
        membership.resign(MID)
        with pytest.raises(Refused):
            membership.resign(MID)

    def test_paying_after_resignation_is_refused(self):
        membership = _membership()
        membership.resign(MID)
        with pytest.raises(Refused):
            membership.pay(Money.of(10, "USD"))


class TestLapseAndRejoin:
    def test_a_membership_lapses_after_the_year(self):
        membership = _membership()
        assert membership.lapse(AFTER) is MemberState.LAPSED
        assert not membership.is_active()

    def test_lapsing_early_is_refused(self):
        membership = _membership()
        with pytest.raises(Refused):
            membership.lapse(MID)

    def test_rejoining_charges_the_joining_fee_again(self):
        membership = _membership()
        membership.lapse(AFTER)
        assert membership.rejoin_cost() == Money.of(170, "USD")

    def test_an_active_member_cannot_rejoin(self):
        with pytest.raises(Refused):
            _membership().rejoin_cost()


class TestConstruction:
    def test_nonpositive_dues_are_refused(self):
        with pytest.raises(Refused):
            _membership(annual_dues=Money.zero("USD"))

    def test_a_backward_year_is_refused(self):
        with pytest.raises(Refused):
            _membership(year_end=YEAR_START)

    def test_payments_accumulate(self):
        membership = _membership()
        membership.pay(Money.of(30, "USD"))
        membership.pay(Money.of(20, "USD"))
        assert membership.dues_paid == Money.of(50, "USD")
