from __future__ import annotations

import pytest

from mint.errors import InsufficientFunds, Refused
from mint.money import Money
from mint.treasury import SweepAccount, apply_sweep, plan_sweep, total_across


def _accounts():
    return [
        SweepAccount("hub", Money.of(1000, "USD"), Money.zero("USD"), Money.zero("USD")),
        SweepAccount(
            "ops", Money.of(5000, "USD"), Money.of(2000, "USD"), Money.of(1000, "USD")
        ),
        SweepAccount(
            "payroll", Money.of(200, "USD"), Money.of(1500, "USD"), Money.of(1000, "USD")
        ),
    ]


class TestSurplusAndShortfall:
    def test_surplus_is_above_target(self):
        accounts = _accounts()
        assert accounts[1].surplus() == Money.of(3000, "USD")

    def test_shortfall_is_below_minimum(self):
        accounts = _accounts()
        assert accounts[2].shortfall() == Money.of(800, "USD")

    def test_an_account_at_target_has_neither(self):
        account = SweepAccount(
            "x", Money.of(100, "USD"), Money.of(100, "USD"), Money.of(50, "USD")
        )
        assert account.surplus().is_zero()
        assert account.shortfall().is_zero()


class TestPlanning:
    def test_surplus_is_pulled_to_the_hub(self):
        plan = plan_sweep(_accounts(), "hub", "USD")
        pulls = [t for t in plan.transfers if t.destination == "hub"]
        assert [t.source for t in pulls] == ["ops"]
        assert pulls[0].amount == Money.of(3000, "USD")

    def test_shortfalls_are_funded_from_the_hub(self):
        plan = plan_sweep(_accounts(), "hub", "USD")
        pushes = [t for t in plan.transfers if t.source == "hub"]
        assert [t.destination for t in pushes] == ["payroll"]
        assert pushes[0].amount == Money.of(800, "USD")

    def test_the_net_change_per_account(self):
        plan = plan_sweep(_accounts(), "hub", "USD")
        assert plan.net_change("ops") == Money.of("-3000.00", "USD")
        assert plan.net_change("payroll") == Money.of(800, "USD")
        assert plan.net_change("hub") == Money.of(2200, "USD")


class TestConservation:
    def test_the_total_across_accounts_is_unchanged(self):
        accounts = _accounts()
        before = total_across({a.code: a.balance for a in accounts}, "USD")
        plan = plan_sweep(accounts, "hub", "USD")
        after = total_across(apply_sweep(accounts, plan), "USD")
        assert before == after

    def test_every_account_ends_at_or_above_its_minimum(self):
        accounts = _accounts()
        plan = plan_sweep(accounts, "hub", "USD")
        result = apply_sweep(accounts, plan)
        for account in accounts:
            assert result[account.code] >= account.minimum


class TestRefusals:
    def test_an_unfundable_sweep_is_refused_rather_than_partial(self):
        accounts = [
            SweepAccount("hub", Money.zero("USD"), Money.zero("USD"), Money.zero("USD")),
            SweepAccount(
                "a", Money.zero("USD"), Money.of(100, "USD"), Money.of(100, "USD")
            ),
        ]
        with pytest.raises(InsufficientFunds) as caught:
            plan_sweep(accounts, "hub", "USD")
        assert "state nobody chose" in str(caught.value)

    def test_a_missing_hub_is_refused(self):
        with pytest.raises(Refused):
            plan_sweep(_accounts(), "nowhere", "USD")

    def test_a_minimum_above_target_is_refused(self):
        with pytest.raises(Refused) as caught:
            SweepAccount(
                "x", Money.of(10, "USD"), Money.of(10, "USD"), Money.of(50, "USD")
            )
        assert "fight itself" in str(caught.value)

    def test_a_wrong_currency_account_is_refused(self):
        accounts = [
            SweepAccount("hub", Money.zero("USD"), Money.zero("USD"), Money.zero("USD")),
            SweepAccount("e", Money.of(1, "EUR"), Money.zero("EUR"), Money.zero("EUR")),
        ]
        with pytest.raises(Refused):
            plan_sweep(accounts, "hub", "USD")
