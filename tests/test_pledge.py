from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.pledge import Pledge, PledgeRegister

PROMISED = datetime.date(2026, 1, 1)


def _pledge(**kwargs) -> Pledge:
    base = {
        "id": "P-1",
        "donor": "a donor",
        "amount": Money.of(100000, "USD"),
        "promised_on": PROMISED,
        "conditional": False,
    }
    base.update(kwargs)
    return Pledge(**base)


class TestConditionality:
    def test_an_unconditional_pledge_is_an_asset_at_once(self):
        assert _pledge().is_recognizable()
        assert _pledge().present_value() == Money.of(100000, "USD")

    def test_a_conditional_pledge_is_not(self):
        pledge = _pledge(conditional=True)
        assert not pledge.is_recognizable()
        assert pledge.present_value().is_zero()

    def test_meeting_the_condition_makes_it_one(self):
        pledge = _pledge(conditional=True)
        pledge.meet_condition()
        assert pledge.is_recognizable()

    def test_collecting_against_a_conditional_pledge_is_refused(self):
        pledge = _pledge(conditional=True)
        with pytest.raises(Refused) as caught:
            pledge.collect(Money.of(1000, "USD"))
        assert "nothing to collect against yet" in str(caught.value)

    def test_an_unconditional_pledge_has_no_condition_to_meet(self):
        with pytest.raises(Refused):
            _pledge().meet_condition()


class TestDiscounting:
    def test_a_single_year_pledge_is_undiscounted(self):
        pledge = _pledge(discount_rate=Fraction(5, 100))
        assert pledge.present_value() == pledge.amount
        assert pledge.discount().is_zero()

    def test_a_multi_year_pledge_is_worth_less_than_its_face(self):
        pledge = _pledge(years_to_collect=5, discount_rate=Fraction(5, 100))
        assert pledge.present_value() < pledge.amount
        assert pledge.discount().is_positive()

    def test_a_zero_rate_leaves_it_undiscounted(self):
        pledge = _pledge(years_to_collect=5)
        assert pledge.present_value() == pledge.amount

    def test_a_negative_rate_is_refused(self):
        with pytest.raises(Refused):
            _pledge(discount_rate=Fraction(-1, 100))


class TestCollection:
    def test_collecting_reduces_the_outstanding(self):
        pledge = _pledge()
        pledge.collect(Money.of(40000, "USD"))
        assert pledge.outstanding() == Money.of(60000, "USD")

    def test_collecting_the_whole_settles_it(self):
        pledge = _pledge()
        pledge.collect(Money.of(100000, "USD"))
        assert pledge.is_settled()

    def test_over_collecting_is_refused(self):
        with pytest.raises(Refused):
            _pledge().collect(Money.of(200000, "USD"))


class TestRegister:
    def _register(self) -> PledgeRegister:
        register = PledgeRegister("USD", uncollectible_rate=Fraction(10, 100))
        register.add(_pledge())
        register.add(_pledge(id="P-2", amount=Money.of(50000, "USD")))
        register.add(_pledge(id="P-3", amount=Money.of(20000, "USD"), conditional=True))
        return register

    def test_only_recognizable_pledges_are_receivable(self):
        register = self._register()
        assert len(register.recognizable()) == 2
        assert register.gross_receivable() == Money.of(150000, "USD")

    def test_unrecognized_pledges_are_reported_separately(self):
        assert self._register().unrecognized_total() == Money.of(20000, "USD")

    def test_an_allowance_is_held_against_the_receivable(self):
        register = self._register()
        assert register.allowance() == Money.of(15000, "USD")
        assert register.carrying_value() == Money.of(135000, "USD")

    def test_collections_reduce_the_receivable(self):
        register = self._register()
        register.pledges[0].collect(Money.of(100000, "USD"))
        assert register.gross_receivable() == Money.of(50000, "USD")

    def test_a_duplicate_pledge_is_refused(self):
        register = self._register()
        with pytest.raises(Refused):
            register.add(_pledge())

    def test_a_wrong_currency_pledge_is_refused(self):
        register = self._register()
        with pytest.raises(Refused):
            register.add(_pledge(id="P-9", amount=Money.of(100, "EUR")))

    def test_an_uncollectible_rate_of_one_is_refused(self):
        with pytest.raises(Refused):
            PledgeRegister("USD", uncollectible_rate=Fraction(1))
