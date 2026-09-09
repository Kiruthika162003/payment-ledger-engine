from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.sinkingfund import Deposit, SinkingFund

START = datetime.date(2026, 1, 1)


def _fund(**kwargs) -> SinkingFund:
    base = {
        "name": "2031 notes",
        "target": Money.of(100000, "USD"),
        "periods": 5,
        "period_rate": Fraction(5, 100),
        "started_on": START,
    }
    base.update(kwargs)
    return SinkingFund(**base)


def _year(offset: int) -> datetime.date:
    return datetime.date(2026 + offset, 1, 1)


class TestRequiredDeposit:
    def test_the_deposits_reach_the_target(self):
        fund = _fund()
        assert fund.reaches_target()

    def test_a_zero_rate_divides_the_target_evenly(self):
        fund = _fund(period_rate=Fraction(0))
        assert fund.required_deposit() == Money.of(20000, "USD")

    def test_interest_lowers_the_required_deposit(self):
        assert _fund().required_deposit() < _fund(
            period_rate=Fraction(0)
        ).required_deposit()

    def test_the_deposit_rounds_up_not_down(self):
        fund = _fund()
        # Rounded up so the fund is never a few cents short on the one day
        # it must not be short.
        assert fund.projected_balance() >= fund.target

    def test_the_accumulation_factor_counts_the_periods(self):
        assert _fund(period_rate=Fraction(0)).accumulation_factor() == Fraction(5)


class TestSchedule:
    def test_every_row_reconciles(self):
        assert all(row.reconciles() for row in _fund().schedule())

    def test_the_first_period_earns_nothing(self):
        rows = _fund().schedule()
        assert rows[0].earnings.is_zero()

    def test_the_schedule_has_one_row_per_period(self):
        assert len(_fund().schedule()) == 5

    def test_the_last_closing_is_the_projection(self):
        fund = _fund()
        assert fund.schedule()[-1].closing == fund.projected_balance()

    def test_a_smaller_deposit_falls_short(self):
        fund = _fund()
        small = Money.of(10000, "USD")
        assert not fund.reaches_target(small)
        assert fund.shortfall(small).is_positive()

    def test_a_larger_deposit_leaves_a_surplus(self):
        fund = _fund()
        assert fund.surplus(Money.of(30000, "USD")).is_positive()
        assert fund.surplus().is_positive() or fund.surplus().is_zero()


class TestActualDeposits:
    def test_the_balance_grows_from_what_was_actually_paid(self):
        fund = _fund()
        fund.deposit(_year(1), Money.of(20000, "USD"))
        fund.deposit(_year(2), Money.of(20000, "USD"))
        assert fund.balance_at(_year(2)) == Money.of(41000, "USD")

    def test_deposits_accumulate(self):
        fund = _fund()
        fund.deposit(_year(1), Money.of(1000, "USD"))
        fund.deposit(_year(2), Money.of(2000, "USD"))
        assert fund.deposited() == Money.of(3000, "USD")

    def test_a_deposit_before_the_fund_started_is_refused(self):
        fund = _fund()
        with pytest.raises(Refused) as caught:
            fund.deposit(datetime.date(2025, 6, 1), Money.of(100, "USD"))
        assert "predates the fund" in str(caught.value)

    def test_a_nonpositive_deposit_is_refused(self):
        with pytest.raises(Refused):
            Deposit(START, Money.zero("USD"))

    def test_a_wrong_currency_deposit_is_refused(self):
        fund = _fund()
        with pytest.raises(Refused):
            fund.deposit(_year(1), Money.of(100, "EUR"))


class TestCompliance:
    def test_an_untouched_fund_is_on_schedule(self):
        assert _fund().is_on_schedule(START)

    def test_paying_the_required_deposit_keeps_it_on_schedule(self):
        fund = _fund()
        fund.deposit(_year(1), fund.required_deposit())
        assert fund.is_on_schedule(_year(1))

    def test_underpaying_falls_behind(self):
        fund = _fund()
        fund.deposit(_year(1), Money.of(1000, "USD"))
        assert not fund.is_on_schedule(_year(1))

    def test_the_catch_up_deposit_repairs_the_shortfall(self):
        fund = _fund()
        fund.deposit(_year(1), Money.of(1000, "USD"))
        catch_up = fund.catch_up_deposit(_year(1))
        assert catch_up > fund.required_deposit()

    def test_a_fund_already_ahead_needs_no_catch_up(self):
        fund = _fund()
        fund.deposit(_year(1), Money.of(90000, "USD"))
        assert fund.catch_up_deposit(_year(1)).is_zero()

    def test_a_finished_fund_reports_its_remaining_deficit(self):
        fund = _fund(periods=1)
        fund.deposit(_year(1), Money.of(40000, "USD"))
        assert fund.catch_up_deposit(_year(1)) == Money.of(60000, "USD")


class TestConstruction:
    def test_a_nonpositive_target_is_refused(self):
        with pytest.raises(Refused):
            _fund(target=Money.zero("USD"))

    def test_zero_periods_are_refused(self):
        with pytest.raises(Refused):
            _fund(periods=0)

    def test_a_negative_rate_is_refused(self):
        with pytest.raises(Refused) as caught:
            _fund(period_rate=Fraction(-1, 100))
        assert "shrink toward its target" in str(caught.value)

    def test_periods_elapsed_counts_the_deposits_made(self):
        fund = _fund()
        fund.deposit(_year(1), Money.of(100, "USD"))
        assert fund.periods_elapsed(_year(1)) == 1
        assert fund.periods_elapsed(datetime.date(2025, 1, 1)) == 0
