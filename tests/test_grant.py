from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.grant import Grant, GrantKind, GrantRegister
from mint.money import Money

RECEIVED = datetime.date(2026, 1, 1)
BREACH_DAY = datetime.date(2027, 6, 1)


def _grant(**kwargs) -> Grant:
    base = {
        "id": "G-1",
        "amount": Money.of(60000, "USD"),
        "kind": GrantKind.ASSET_RELATED,
        "received": RECEIVED,
        "periods": 5,
    }
    base.update(kwargs)
    return Grant(**base)


class TestRelease:
    def test_nothing_is_recognized_on_receipt(self):
        grant = _grant()
        assert grant.released.is_zero()
        assert grant.deferred_balance() == Money.of(60000, "USD")

    def test_each_period_releases_a_share(self):
        grant = _grant()
        assert grant.release_next() == Money.of(12000, "USD")
        assert grant.deferred_balance() == Money.of(48000, "USD")

    def test_the_releases_sum_to_the_grant(self):
        grant = _grant()
        for _ in range(5):
            grant.release_next()
        assert grant.is_fully_released()
        assert grant.released == Money.of(60000, "USD")

    def test_an_awkward_grant_still_closes(self):
        grant = _grant(amount=Money.of("10000.01", "USD"), periods=3)
        for _ in range(3):
            grant.release_next()
        assert grant.deferred_balance().is_zero()

    def test_releasing_past_the_end_is_refused(self):
        grant = _grant(periods=1)
        grant.release_next()
        with pytest.raises(Refused):
            grant.release_next()

    def test_a_single_period_grant_is_allowed(self):
        grant = _grant(periods=1)
        assert grant.release_next() == Money.of(60000, "USD")

    def test_a_zero_period_grant_is_refused(self):
        with pytest.raises(Refused) as caught:
            _grant(periods=0)
        assert "mismatch the rule exists to prevent" in str(caught.value)


class TestBreach:
    def test_a_breach_makes_the_deferred_balance_repayable(self):
        grant = _grant()
        grant.release_next()
        repayable = grant.breach(BREACH_DAY)
        assert repayable == Money.of(48000, "USD")
        assert grant.is_breached()

    def test_a_clawback_reclaims_what_was_recognized_too(self):
        grant = _grant()
        grant.release_next()
        repayable = grant.breach(BREACH_DAY, claw_back_recognized=True)
        assert repayable == Money.of(60000, "USD")

    def test_releasing_after_a_breach_is_refused(self):
        grant = _grant()
        grant.breach(BREACH_DAY)
        with pytest.raises(Refused) as caught:
            grant.release_next()
        assert "already been lost" in str(caught.value)

    def test_breaching_twice_is_refused(self):
        grant = _grant()
        grant.breach(BREACH_DAY)
        with pytest.raises(Refused):
            grant.breach(BREACH_DAY)

    def test_an_unbreached_grant_owes_nothing(self):
        assert _grant().repayable().is_zero()


class TestBulkRelease:
    def test_the_remainder_can_be_released_at_once(self):
        grant = _grant()
        grant.release_next()
        assert grant.release_all_remaining() == Money.of(48000, "USD")
        assert grant.is_fully_released()

    def test_releasing_nothing_is_refused(self):
        grant = _grant()
        grant.release_all_remaining()
        with pytest.raises(Refused):
            grant.release_all_remaining()


class TestRegister:
    def _register(self) -> GrantRegister:
        register = GrantRegister("USD")
        register.add(_grant())
        register.add(_grant(id="G-2", kind=GrantKind.INCOME_RELATED,
                            amount=Money.of(10000, "USD"), periods=2))
        return register

    def test_totals_across_grants(self):
        register = self._register()
        assert register.total_deferred() == Money.of(70000, "USD")
        register.grants[0].release_next()
        assert register.total_released() == Money.of(12000, "USD")

    def test_grants_filter_by_kind(self):
        assert len(self._register().of_kind(GrantKind.INCOME_RELATED)) == 1

    def test_the_repayable_total_follows_breaches(self):
        register = self._register()
        register.grants[0].breach(BREACH_DAY)
        assert register.total_repayable() == Money.of(60000, "USD")

    def test_a_duplicate_grant_is_refused(self):
        register = self._register()
        with pytest.raises(Refused):
            register.add(_grant())

    def test_a_wrong_currency_grant_is_refused(self):
        register = self._register()
        with pytest.raises(Refused):
            register.add(_grant(id="G-9", amount=Money.of(100, "EUR")))
