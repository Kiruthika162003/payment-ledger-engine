from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.fundaccounting import Fund, FundLedger, Restriction
from mint.money import Money

DAY = datetime.date(2026, 5, 1)


def _ledger() -> FundLedger:
    ledger = FundLedger("USD")
    ledger.open(Fund("GEN", "General", Restriction.UNRESTRICTED, "USD"))
    ledger.open(
        Fund("WELL", "Well Project", Restriction.RESTRICTED, "USD", purpose="wells")
    )
    ledger.open(Fund("ENDOW", "Endowment", Restriction.ENDOWMENT, "USD"))
    ledger.get("GEN").receive(Money.of(50000, "USD"), DAY, "general giving")
    ledger.get("WELL").receive(Money.of(30000, "USD"), DAY, "well appeal")
    ledger.get("ENDOW").receive(Money.of(100000, "USD"), DAY, "legacy")
    return ledger


class TestSeparation:
    def test_funds_hold_their_own_balances(self):
        ledger = _ledger()
        assert ledger.get("WELL").balance() == Money.of(30000, "USD")
        assert ledger.total(Restriction.RESTRICTED) == Money.of(30000, "USD")

    def test_the_grand_total_covers_them_all(self):
        assert _ledger().grand_total() == Money.of(180000, "USD")

    def test_a_restricted_fund_needs_a_purpose(self):
        with pytest.raises(Refused) as caught:
            Fund("X", "Vague", Restriction.RESTRICTED, "USD")
        assert "nothing can be checked" in str(caught.value)

    def test_an_endowment_may_not_be_spent_on_anything(self):
        ledger = _ledger()
        assert not ledger.get("ENDOW").may_spend_on("wells")
        assert not ledger.get("ENDOW").may_spend_on("anything")

    def test_unrestricted_money_may_go_anywhere(self):
        assert _ledger().get("GEN").may_spend_on("wells")


class TestRelease:
    def test_a_qualifying_release_moves_money_between_funds(self):
        ledger = _ledger()
        ledger.release("WELL", "GEN", Money.of(12000, "USD"), "wells", DAY)
        assert ledger.get("WELL").balance() == Money.of(18000, "USD")
        assert ledger.get("GEN").balance() == Money.of(62000, "USD")

    def test_a_release_creates_no_money(self):
        ledger = _ledger()
        before = ledger.grand_total()
        ledger.release("WELL", "GEN", Money.of(12000, "USD"), "wells", DAY)
        assert ledger.grand_total() == before

    def test_the_wrong_purpose_is_a_breach(self):
        ledger = _ledger()
        with pytest.raises(Refused) as caught:
            ledger.release("WELL", "GEN", Money.of(1000, "USD"), "salaries", DAY)
        assert "not a reallocation" in str(caught.value)

    def test_releasing_more_than_was_given_is_refused(self):
        ledger = _ledger()
        with pytest.raises(Refused):
            ledger.release("WELL", "GEN", Money.of(90000, "USD"), "wells", DAY)

    def test_releasing_into_a_restricted_fund_is_refused(self):
        ledger = _ledger()
        with pytest.raises(Refused):
            ledger.release("WELL", "ENDOW", Money.of(100, "USD"), "wells", DAY)

    def test_releases_are_tracked(self):
        ledger = _ledger()
        ledger.release("WELL", "GEN", Money.of(5000, "USD"), "wells", DAY)
        ledger.release("WELL", "GEN", Money.of(3000, "USD"), "wells", DAY)
        assert ledger.released_total() == Money.of(8000, "USD")


class TestOverdrawn:
    def test_a_healthy_ledger_has_no_overdrawn_funds(self):
        assert _ledger().overdrawn() == []

    def test_an_overdrawn_fund_is_named(self):
        ledger = _ledger()
        ledger.get("WELL").movements.append(
            type(ledger.get("WELL").movements[0])(
                DAY, Money.of("-40000.00", "USD"), "overspent"
            )
        )
        assert "WELL" in ledger.overdrawn()
        assert ledger.get("WELL").is_overdrawn()


class TestRefusals:
    def test_a_duplicate_fund_is_refused(self):
        ledger = _ledger()
        with pytest.raises(Refused):
            ledger.open(Fund("GEN", "Again", Restriction.UNRESTRICTED, "USD"))

    def test_a_wrong_currency_fund_is_refused(self):
        ledger = _ledger()
        with pytest.raises(Refused):
            ledger.open(Fund("EUR1", "Euro", Restriction.UNRESTRICTED, "EUR"))

    def test_an_unknown_fund_is_refused(self):
        with pytest.raises(Refused):
            _ledger().get("NOPE")

    def test_a_nonpositive_gift_is_refused(self):
        with pytest.raises(Refused):
            _ledger().get("GEN").receive(Money.zero("USD"), DAY, "nothing")
