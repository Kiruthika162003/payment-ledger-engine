from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.reserve import RollingReserve

DAY1 = datetime.date(2026, 1, 1)
DAY10 = datetime.date(2026, 1, 10)
DAY91 = datetime.date(2026, 4, 1)
DAY100 = datetime.date(2026, 4, 10)


def _reserve() -> RollingReserve:
    return RollingReserve(rate=Fraction(1, 10), hold_days=90, currency="USD")


class TestWithholding:
    def test_the_rate_is_withheld_from_the_settlement(self):
        reserve = _reserve()
        item = reserve.withhold("s1", Money.of(1000, "USD"), DAY1)
        assert item.withheld == Money.of(100, "USD")
        assert reserve.payout_for("s1") == Money.of(900, "USD")

    def test_the_release_date_is_the_hold_period_out(self):
        item = _reserve().withhold("s1", Money.of(1000, "USD"), DAY1)
        assert item.releases_on == datetime.date(2026, 4, 1)

    def test_withholding_twice_on_one_settlement_is_refused(self):
        reserve = _reserve()
        reserve.withhold("s1", Money.of(1000, "USD"), DAY1)
        with pytest.raises(Refused):
            reserve.withhold("s1", Money.of(1000, "USD"), DAY1)


class TestRolling:
    def test_each_tranche_matures_on_its_own_schedule(self):
        reserve = _reserve()
        reserve.withhold("s1", Money.of(1000, "USD"), DAY1)
        reserve.withhold("s2", Money.of(1000, "USD"), DAY10)
        due = reserve.due_for_release(DAY91)
        assert [item.settlement_id for item in due] == ["s1"]

    def test_the_balance_holds_what_has_not_matured(self):
        reserve = _reserve()
        reserve.withhold("s1", Money.of(1000, "USD"), DAY1)
        reserve.withhold("s2", Money.of(1000, "USD"), DAY10)
        assert reserve.balance(DAY1) == Money.of(200, "USD")
        assert reserve.balance(DAY91) == Money.of(100, "USD")

    def test_releasing_pays_out_the_matured_tranche(self):
        reserve = _reserve()
        reserve.withhold("s1", Money.of(1000, "USD"), DAY1)
        assert reserve.release(DAY91) == Money.of(100, "USD")
        assert reserve.release(DAY91).is_zero()

    def test_every_dollar_withheld_is_eventually_released_once(self):
        reserve = _reserve()
        reserve.withhold("s1", Money.of(1000, "USD"), DAY1)
        reserve.withhold("s2", Money.of(500, "USD"), DAY10)
        reserve.release(DAY100)
        assert reserve.released_total() == reserve.withheld_total()
        assert reserve.balance(DAY100).is_zero()


class TestRefusals:
    def test_a_full_withholding_is_refused_as_a_freeze(self):
        with pytest.raises(Refused) as caught:
            RollingReserve(rate=Fraction(1), hold_days=90, currency="USD")
        assert "it is a freeze" in str(caught.value)

    def test_a_zero_hold_period_is_refused(self):
        with pytest.raises(Refused):
            RollingReserve(rate=Fraction(1, 10), hold_days=0, currency="USD")

    def test_a_wrong_currency_settlement_is_refused(self):
        with pytest.raises(Refused):
            _reserve().withhold("s1", Money.of(1000, "EUR"), DAY1)
