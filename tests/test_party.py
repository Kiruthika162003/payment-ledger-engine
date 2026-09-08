from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.party import Party, PartyRegistry, PartyRole

DAY = datetime.date(2026, 1, 1)


def _party(role: PartyRole = PartyRole.CUSTOMER) -> Party:
    return Party("c1", "Acme", role, "USD")


class TestBalance:
    def test_charges_and_credits_move_the_balance(self):
        party = _party()
        party.charge(Money.of(500, "USD"), DAY)
        party.credit(Money.of(200, "USD"), DAY)
        assert party.balance() == Money.of(300, "USD")

    def test_settling_zeroes_the_balance(self):
        party = _party()
        party.charge(Money.of(100, "USD"), DAY)
        party.credit(Money.of(100, "USD"), DAY)
        assert party.is_settled()

    def test_a_credit_past_the_balance_is_refused(self):
        party = _party()
        party.charge(Money.of(100, "USD"), DAY)
        with pytest.raises(Refused) as caught:
            party.credit(Money.of(150, "USD"), DAY)
        assert "not by a typo" in str(caught.value)

    def test_a_wrong_currency_movement_is_refused(self):
        with pytest.raises(Refused):
            _party().charge(Money.of(10, "EUR"), DAY)


class TestRegistry:
    def test_parties_register_and_resolve(self):
        registry = PartyRegistry()
        registry.add(_party())
        assert registry.get("c1").name == "Acme"

    def test_a_duplicate_registration_is_refused(self):
        registry = PartyRegistry()
        registry.add(_party())
        with pytest.raises(Refused):
            registry.add(_party())

    def test_an_unknown_party_is_refused(self):
        with pytest.raises(Refused):
            PartyRegistry().get("nobody")

    def test_a_both_role_party_appears_under_each_role(self):
        registry = PartyRegistry()
        registry.add(Party("x", "Dual", PartyRole.BOTH, "USD"))
        assert len(registry.of_role(PartyRole.CUSTOMER)) == 1
        assert len(registry.of_role(PartyRole.VENDOR)) == 1

    def test_total_owed_sums_one_currency(self):
        registry = PartyRegistry()
        first = registry.add(Party("a", "A", PartyRole.CUSTOMER, "USD"))
        second = registry.add(Party("b", "B", PartyRole.CUSTOMER, "USD"))
        registry.add(Party("c", "C", PartyRole.CUSTOMER, "EUR"))
        first.charge(Money.of(100, "USD"), DAY)
        second.charge(Money.of(50, "USD"), DAY)
        assert registry.total_owed(PartyRole.CUSTOMER, "USD") == Money.of(150, "USD")


class TestNetting:
    def test_netting_across_registries_is_explicit(self):
        receivables = PartyRegistry()
        payables = PartyRegistry()
        customer = receivables.add(Party("acme", "Acme", PartyRole.CUSTOMER, "USD"))
        vendor = payables.add(Party("acme", "Acme", PartyRole.VENDOR, "USD"))
        customer.charge(Money.of(500, "USD"), DAY)
        vendor.charge(Money.of(200, "USD"), DAY)
        assert receivables.net_position("acme", payables) == Money.of(300, "USD")
