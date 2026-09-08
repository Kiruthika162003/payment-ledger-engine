from __future__ import annotations

import datetime

import pytest

from mint.collections import PaymentPlan, Promise, PromiseState
from mint.errors import Refused
from mint.money import Money

DUE = datetime.date(2026, 3, 1)
AFTER = datetime.date(2026, 3, 5)
BEFORE = datetime.date(2026, 2, 25)


class TestPromise:
    def test_an_unpaid_promise_is_open_before_its_date(self):
        promise = Promise("p1", Money.of(100, "USD"), DUE)
        assert promise.state(BEFORE) is PromiseState.OPEN

    def test_a_paid_promise_is_kept(self):
        promise = Promise("p1", Money.of(100, "USD"), DUE)
        promise.record_payment(Money.of(100, "USD"))
        assert promise.state(AFTER) is PromiseState.KEPT

    def test_an_unpaid_promise_breaks_after_its_date(self):
        promise = Promise("p1", Money.of(100, "USD"), DUE)
        assert promise.state(AFTER) is PromiseState.BROKEN

    def test_a_partly_paid_promise_is_partly_kept(self):
        promise = Promise("p1", Money.of(100, "USD"), DUE)
        promise.record_payment(Money.of(40, "USD"))
        assert promise.state(AFTER) is PromiseState.PARTLY_KEPT
        assert promise.shortfall() == Money.of(60, "USD")

    def test_state_comes_from_payments_not_a_flag(self):
        promise = Promise("p1", Money.of(100, "USD"), DUE)
        promise.record_payment(Money.of(100, "USD"))
        # Kept even before the due date, because the money arrived.
        assert promise.state(BEFORE) is PromiseState.KEPT

    def test_a_nonpositive_promise_is_refused(self):
        with pytest.raises(Refused):
            Promise("p1", Money.zero("USD"), DUE)


class TestPlan:
    def _plan(self) -> PaymentPlan:
        plan = PaymentPlan("PL-1", Money.of(1200, "USD"))
        plan.build(6, DUE, 30)
        return plan

    def test_the_instalments_clear_the_debt(self):
        plan = self._plan()
        assert plan.covers_the_debt()
        assert len(plan.instalments) == 6

    def test_an_awkward_debt_still_clears(self):
        plan = PaymentPlan("PL-2", Money.of("1000.00", "USD"))
        plan.build(3, DUE, 30)
        assert plan.covers_the_debt()

    def test_payments_reduce_the_outstanding(self):
        plan = self._plan()
        plan.get("PL-1-1").record_payment(Money.of(200, "USD"))
        assert plan.outstanding() == Money.of(1000, "USD")

    def test_the_next_due_instalment_is_named(self):
        plan = self._plan()
        assert plan.next_due(BEFORE).id == "PL-1-1"

    def test_a_settled_plan_has_nothing_next(self):
        plan = self._plan()
        for instalment in plan.instalments:
            instalment.record_payment(instalment.amount)
        assert plan.is_settled()
        assert plan.next_due(AFTER) is None


class TestMisses:
    def _plan(self) -> PaymentPlan:
        plan = PaymentPlan("PL-1", Money.of(1200, "USD"), misses_allowed=2)
        plan.build(6, DUE, 30)
        return plan

    def test_one_miss_does_not_void_the_plan(self):
        plan = self._plan()
        later = DUE + datetime.timedelta(days=5)
        assert plan.misses(later) == 1
        assert not plan.has_failed(later)

    def test_the_plan_fails_past_the_allowance(self):
        plan = self._plan()
        much_later = DUE + datetime.timedelta(days=95)
        assert plan.misses(much_later) >= 3
        assert plan.has_failed(much_later)

    def test_paying_on_time_avoids_misses(self):
        plan = self._plan()
        for instalment in plan.instalments:
            instalment.record_payment(instalment.amount)
        assert plan.misses(DUE + datetime.timedelta(days=200)) == 0


class TestRefusals:
    def test_a_zero_instalment_plan_is_refused(self):
        with pytest.raises(Refused):
            PaymentPlan("PL-1", Money.of(100, "USD")).build(0, DUE, 30)

    def test_a_zero_interval_is_refused(self):
        with pytest.raises(Refused):
            PaymentPlan("PL-1", Money.of(100, "USD")).build(3, DUE, 0)

    def test_an_unknown_instalment_is_refused(self):
        plan = PaymentPlan("PL-1", Money.of(120, "USD"))
        plan.build(2, DUE, 30)
        with pytest.raises(Refused):
            plan.get("PL-1-9")
