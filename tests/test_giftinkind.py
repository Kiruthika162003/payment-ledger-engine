from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.giftinkind import DonatedGoods, DonatedService, InKindRegister
from mint.money import Money

DAY = datetime.date(2026, 4, 1)


def _audit() -> DonatedService:
    return DonatedService(
        description="donated audit",
        hours=Fraction(40),
        hourly_rate=Money.of(200, "USD"),
        requires_specialist_skill=True,
        would_have_been_purchased=True,
        provider_has_the_skill=True,
    )


def _envelopes(**kwargs) -> DonatedService:
    base = {
        "description": "envelope stuffing",
        "hours": Fraction(100),
        "hourly_rate": Money.of(15, "USD"),
        "requires_specialist_skill": False,
        "would_have_been_purchased": False,
        "provider_has_the_skill": True,
    }
    base.update(kwargs)
    return DonatedService(**base)


def _register() -> InKindRegister:
    register = InKindRegister("USD")
    register.receive_goods(DonatedGoods("a van", Money.of(12000, "USD"), DAY))
    register.receive_service(_audit())
    register.receive_service(_envelopes())
    return register


class TestGoods:
    def test_donated_goods_are_income_at_fair_value(self):
        assert _register().goods_income() == Money.of(12000, "USD")

    def test_a_nonpositive_valuation_is_refused(self):
        with pytest.raises(Refused):
            DonatedGoods("nothing", Money.zero("USD"), DAY)

    def test_goods_need_a_description(self):
        with pytest.raises(Refused):
            DonatedGoods("  ", Money.of(10, "USD"), DAY)

    def test_a_wrong_currency_gift_is_refused(self):
        register = _register()
        with pytest.raises(Refused):
            register.receive_goods(DonatedGoods("euro van", Money.of(1, "EUR"), DAY))


class TestTheThreePartTest:
    def test_a_specialist_service_qualifies(self):
        assert _audit().meets_the_test()
        assert _audit().value() == Money.of(8000, "USD")

    def test_general_volunteering_does_not(self):
        assert not _envelopes().meets_the_test()

    def test_all_three_conditions_are_needed(self):
        service = _envelopes(
            requires_specialist_skill=True, would_have_been_purchased=True
        )
        assert service.meets_the_test()
        without = _envelopes(requires_specialist_skill=True)
        assert not without.meets_the_test()

    def test_the_failed_conditions_are_named(self):
        failures = _envelopes().failed_conditions()
        assert len(failures) == 2
        assert any("specialist skill" in reason for reason in failures)

    def test_valuing_a_failing_service_is_refused(self):
        with pytest.raises(Refused) as caught:
            _envelopes().value()
        assert "grow without limit" in str(caught.value)

    def test_a_service_with_no_hours_is_refused(self):
        with pytest.raises(Refused):
            _envelopes(hours=Fraction(0))


class TestRegister:
    def test_only_qualifying_services_are_income(self):
        register = _register()
        assert register.services_income() == Money.of(8000, "USD")

    def test_total_in_kind_income_covers_both(self):
        assert _register().total_in_kind_income() == Money.of(20000, "USD")

    def test_unrecognized_hours_are_still_reported(self):
        register = _register()
        assert register.volunteer_hours() == Fraction(100)
        assert register.recognized_hours() == Fraction(40)

    def test_the_two_service_lists_are_separated(self):
        register = _register()
        assert len(register.recognizable_services()) == 1
        assert len(register.unrecognizable_services()) == 1

    def test_a_wrong_currency_service_is_refused(self):
        register = _register()
        with pytest.raises(Refused):
            register.receive_service(_envelopes(hourly_rate=Money.of(10, "EUR")))
