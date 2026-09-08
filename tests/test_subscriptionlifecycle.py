from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.subscriptionlifecycle import State, Subscription

START = datetime.date(2026, 1, 1)
MID = datetime.date(2026, 1, 16)
NEXT = datetime.date(2026, 2, 1)


def _subscription(**kwargs) -> Subscription:
    base = {"id": "S-1", "price": Money.of(30, "USD"), "started": START}
    base.update(kwargs)
    return Subscription(**base)


class TestTrial:
    def test_a_new_subscription_is_trialing(self):
        assert _subscription().state is State.TRIALING

    def test_converting_starts_a_billing_period(self):
        subscription = _subscription()
        subscription.convert(START)
        assert subscription.state is State.ACTIVE
        assert subscription.period_end == NEXT

    def test_converting_twice_is_refused(self):
        subscription = _subscription()
        subscription.convert(START)
        with pytest.raises(Refused):
            subscription.convert(START)

    def test_a_trial_can_be_cancelled(self):
        subscription = _subscription()
        assert subscription.cancel(START) is State.CANCELLED


class TestFailedPayments:
    def test_a_failure_moves_to_past_due_not_cancelled(self):
        subscription = _subscription()
        subscription.convert(START)
        assert subscription.payment_failed(NEXT) is State.PAST_DUE

    def test_it_stays_past_due_across_retries(self):
        subscription = _subscription()
        subscription.convert(START)
        subscription.payment_failed(NEXT)
        assert subscription.payment_failed(NEXT) is State.PAST_DUE

    def test_exhausting_the_retries_cancels(self):
        subscription = _subscription(max_attempts=3)
        subscription.convert(START)
        subscription.payment_failed(NEXT)
        subscription.payment_failed(NEXT)
        assert subscription.payment_failed(NEXT) is State.CANCELLED

    def test_a_recovery_returns_it_to_active(self):
        subscription = _subscription()
        subscription.convert(START)
        subscription.payment_failed(NEXT)
        assert subscription.payment_succeeded(NEXT) is State.ACTIVE
        assert subscription.failed_attempts == 0

    def test_days_past_due_counts_from_the_period_end(self):
        subscription = _subscription()
        subscription.convert(START)
        subscription.payment_failed(NEXT)
        assert subscription.days_past_due(datetime.date(2026, 2, 11)) == 10

    def test_a_cancelled_subscription_is_not_billed(self):
        subscription = _subscription()
        subscription.cancel(START)
        with pytest.raises(Refused):
            subscription.payment_failed(START)


class TestCancellation:
    def test_an_immediate_cancellation_refunds_the_unused_slice(self):
        subscription = _subscription()
        subscription.convert(START)
        subscription.cancel(MID)
        assert subscription.refund_due(MID).is_positive()

    def test_an_end_of_period_cancellation_stays_active(self):
        subscription = _subscription()
        subscription.convert(START)
        subscription.cancel(MID, immediately=False)
        assert subscription.state is State.ACTIVE
        assert subscription.cancel_at_period_end

    def test_an_active_subscription_owes_no_refund(self):
        subscription = _subscription()
        subscription.convert(START)
        assert subscription.refund_due(MID).is_zero()

    def test_cancelling_twice_is_refused(self):
        subscription = _subscription()
        subscription.cancel(START)
        with pytest.raises(Refused):
            subscription.cancel(START)


class TestReactivation:
    def test_reactivating_starts_a_new_period(self):
        subscription = _subscription()
        subscription.convert(START)
        subscription.cancel(MID)
        subscription.reactivate(datetime.date(2026, 3, 1))
        assert subscription.state is State.ACTIVE
        assert subscription.period_start == datetime.date(2026, 3, 1)

    def test_reactivating_an_active_subscription_is_refused(self):
        subscription = _subscription()
        subscription.convert(START)
        with pytest.raises(Refused):
            subscription.reactivate(MID)

    def test_the_history_records_every_move(self):
        subscription = _subscription()
        subscription.convert(START)
        subscription.payment_failed(NEXT)
        subscription.payment_succeeded(NEXT)
        assert len(subscription.history) == 3

    def test_billable_states(self):
        subscription = _subscription()
        assert not subscription.is_billable()
        subscription.convert(START)
        assert subscription.is_billable()
