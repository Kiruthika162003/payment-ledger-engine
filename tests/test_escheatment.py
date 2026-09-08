from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.escheatment import (
    ContactKind,
    DormantBalance,
    EscheatmentRegister,
)
from mint.money import Money

OPENED = datetime.date(2020, 1, 15)
LATER = datetime.date(2022, 6, 1)
MUCH_LATER = datetime.date(2026, 1, 1)


def _balance(**kwargs) -> DormantBalance:
    base = {
        "id": "B-1",
        "owner": "alice",
        "amount": Money.of(250, "USD"),
        "opened": OPENED,
    }
    base.update(kwargs)
    return DormantBalance(**base)


class TestClock:
    def test_the_clock_runs_from_opening_without_contact(self):
        assert _balance().dormant_since() == OPENED

    def test_owner_contact_resets_the_clock(self):
        balance = _balance()
        balance.record_contact(LATER, ContactKind.OWNER_INITIATED, "logged in")
        assert balance.dormant_since() == LATER

    def test_system_activity_does_not_reset_it(self):
        balance = _balance()
        balance.record_contact(LATER, ContactKind.SYSTEM_GENERATED, "interest posted")
        assert balance.dormant_since() == OPENED

    def test_a_fee_does_not_count_as_being_heard_from(self):
        balance = _balance()
        balance.record_contact(LATER, ContactKind.SYSTEM_GENERATED, "monthly fee")
        assert balance.reportable_from().year == OPENED.year + 3

    def test_a_contact_needs_a_description(self):
        with pytest.raises(Refused):
            _balance().record_contact(LATER, ContactKind.OWNER_INITIATED, "  ")


class TestDormancy:
    def test_it_becomes_reportable_after_the_period(self):
        balance = _balance()
        assert balance.is_dormant(MUCH_LATER)
        assert not balance.is_dormant(datetime.date(2021, 1, 1))

    def test_the_countdown_is_reported(self):
        balance = _balance()
        assert balance.days_until_reportable(datetime.date(2021, 1, 1)) > 0
        assert balance.days_until_reportable(MUCH_LATER) == 0

    def test_a_longer_dormancy_period_delays_it(self):
        balance = _balance(dormancy_years=10)
        assert not balance.is_dormant(MUCH_LATER)


class TestEscheating:
    def test_a_dormant_balance_can_be_handed_over(self):
        balance = _balance()
        assert balance.escheat(MUCH_LATER) == Money.of(250, "USD")
        assert balance.is_escheated()

    def test_escheating_early_is_refused(self):
        with pytest.raises(Refused) as caught:
            _balance().escheat(datetime.date(2021, 1, 1))
        assert "may still claim" in str(caught.value)

    def test_escheating_twice_is_refused(self):
        balance = _balance()
        balance.escheat(MUCH_LATER)
        with pytest.raises(Refused):
            balance.escheat(MUCH_LATER)


class TestRegister:
    def _register(self) -> EscheatmentRegister:
        register = EscheatmentRegister("USD")
        register.add(_balance())
        register.add(_balance(id="B-2", amount=Money.of(100, "USD")))
        register.add(
            _balance(id="B-3", amount=Money.of(50, "USD"), opened=datetime.date(2025, 1, 1))
        )
        return register

    def test_only_the_dormant_are_reportable(self):
        register = self._register()
        assert len(register.reportable(MUCH_LATER)) == 2

    def test_the_reportable_total(self):
        assert self._register().total_reportable(MUCH_LATER) == Money.of(350, "USD")

    def test_the_held_total_counts_everything_unhandled(self):
        assert self._register().held_total() == Money.of(400, "USD")

    def test_escheated_balances_leave_the_held_total(self):
        register = self._register()
        register.balances[0].escheat(MUCH_LATER)
        assert register.held_total() == Money.of(150, "USD")

    def test_balances_group_by_reporting_year(self):
        buckets = self._register().by_reporting_year()
        assert 2023 in buckets
        assert buckets[2023] == Money.of(350, "USD")

    def test_a_duplicate_balance_is_refused(self):
        register = self._register()
        with pytest.raises(Refused):
            register.add(_balance())

    def test_a_wrong_currency_balance_is_refused(self):
        register = self._register()
        with pytest.raises(Refused):
            register.add(_balance(id="B-9", amount=Money.of(10, "EUR")))
