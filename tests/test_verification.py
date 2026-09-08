from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.verification import CustomerProfile, Tier, TierLimits, standard_limits

DAY = datetime.date(2026, 5, 1)
LATER = datetime.date(2026, 5, 20)
MUCH_LATER = datetime.date(2026, 7, 1)


def _profile(tier: Tier = Tier.UNVERIFIED) -> CustomerProfile:
    return CustomerProfile(
        customer_id="c1", currency="USD", tier=tier, limits=standard_limits("USD")
    )


class TestPerTransaction:
    def test_a_small_transaction_passes(self):
        assert _profile().may_transact(Money.of(100, "USD"), DAY) is None

    def test_a_large_one_is_blocked_at_the_low_tier(self):
        blocked = _profile().may_transact(Money.of(500, "USD"), DAY)
        assert "single-transaction limit" in blocked

    def test_a_higher_tier_permits_it(self):
        assert _profile(Tier.VERIFIED).may_transact(Money.of(500, "USD"), DAY) is None


class TestPeriodLimit:
    def test_many_small_transfers_still_hit_the_period_cap(self):
        profile = _profile()
        for _ in range(2):
            profile.record(Money.of(200, "USD"), DAY)
        blocked = profile.may_transact(Money.of(200, "USD"), DAY)
        assert "over 30 days" in blocked

    def test_activity_ages_out_of_the_window(self):
        profile = _profile()
        profile.record(Money.of(200, "USD"), DAY)
        profile.record(Money.of(200, "USD"), DAY)
        assert profile.spent_in_period(MUCH_LATER).is_zero()
        assert profile.may_transact(Money.of(200, "USD"), MUCH_LATER) is None

    def test_recording_a_blocked_amount_raises(self):
        profile = _profile()
        with pytest.raises(Refused):
            profile.record(Money.of(500, "USD"), DAY)

    def test_spending_accumulates_within_the_window(self):
        profile = _profile()
        profile.record(Money.of(150, "USD"), DAY)
        assert profile.spent_in_period(LATER) == Money.of(150, "USD")


class TestTierChanges:
    def test_an_upgrade_records_its_evidence(self):
        profile = _profile()
        profile.upgrade(Tier.IDENTIFIED, DAY, "passport checked")
        assert profile.tier is Tier.IDENTIFIED
        assert profile.history[-1].evidence == "passport checked"

    def test_an_upgrade_without_evidence_is_refused(self):
        with pytest.raises(Refused) as caught:
            _profile().upgrade(Tier.IDENTIFIED, DAY, "  ")
        assert "granted by mistake" in str(caught.value)

    def test_upgrading_sideways_is_refused(self):
        with pytest.raises(Refused):
            _profile(Tier.VERIFIED).upgrade(Tier.IDENTIFIED, DAY, "evidence")

    def test_a_downgrade_records_its_reason(self):
        profile = _profile(Tier.VERIFIED)
        profile.downgrade(Tier.IDENTIFIED, DAY, "document expired")
        assert profile.tier is Tier.IDENTIFIED

    def test_downgrading_upward_is_refused(self):
        with pytest.raises(Refused):
            _profile().downgrade(Tier.VERIFIED, DAY, "reason")


class TestLimits:
    def test_an_unreachable_per_transaction_limit_is_refused(self):
        with pytest.raises(Refused) as caught:
            TierLimits(Money.of(1000, "USD"), Money.of(100, "USD"), 30)
        assert "unreachable" in str(caught.value)

    def test_a_missing_tier_definition_is_refused(self):
        profile = CustomerProfile("c1", "USD", Tier.ENHANCED, {})
        with pytest.raises(Refused):
            profile.limits_now()

    def test_a_wrong_currency_check_is_refused(self):
        with pytest.raises(Refused):
            _profile().may_transact(Money.of(10, "EUR"), DAY)
