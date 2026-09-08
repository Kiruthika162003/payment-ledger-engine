from __future__ import annotations

import datetime

import pytest

from mint.accounts import AccountType
from mint.approval import ApprovalPolicy, ApprovalState, PendingEntry
from mint.chart import Chart
from mint.entry import entry
from mint.errors import Refused
from mint.ledger import Ledger
from mint.money import Money
from mint.posting import credit, debit

DAY = datetime.date(2026, 4, 1)


def _ledger() -> Ledger:
    chart = Chart()
    chart.add("1000", "Cash", AccountType.ASSET, "USD")
    chart.add("4000", "Sales", AccountType.INCOME, "USD")
    return Ledger(chart)


def _policy() -> ApprovalPolicy:
    return ApprovalPolicy(
        single_signature_below=Money.of(100, "USD"),
        two_approvers_above=Money.of(10000, "USD"),
    )


def _pending(amount: str, maker: str = "alice") -> PendingEntry:
    built = entry(
        [
            debit("1000", Money.of(amount, "USD")),
            credit("4000", Money.of(amount, "USD")),
        ],
        DAY,
    )
    return PendingEntry("E-1", built, maker, _policy())


class TestThresholds:
    def test_a_small_entry_needs_no_approval(self):
        pending = _pending("50.00")
        assert pending.approvals_needed() == 0
        assert pending.submit() is ApprovalState.APPROVED

    def test_a_middling_entry_needs_one(self):
        pending = _pending("500.00")
        assert pending.approvals_needed() == 1
        assert pending.submit() is ApprovalState.PENDING

    def test_a_large_entry_needs_two(self):
        assert _pending("50000.00").approvals_needed() == 2

    def test_contradictory_thresholds_are_refused(self):
        with pytest.raises(Refused):
            ApprovalPolicy(
                single_signature_below=Money.of(10000, "USD"),
                two_approvers_above=Money.of(100, "USD"),
            )


class TestSegregation:
    def test_the_maker_cannot_approve_their_own_entry(self):
        pending = _pending("500.00")
        pending.submit()
        with pytest.raises(Refused) as caught:
            pending.approve("alice", DAY)
        assert "never the checker" in str(caught.value)

    def test_another_person_can(self):
        pending = _pending("500.00")
        pending.submit()
        assert pending.approve("bob", DAY) is ApprovalState.APPROVED

    def test_one_approver_cannot_sign_twice_for_two(self):
        pending = _pending("50000.00")
        pending.submit()
        pending.approve("bob", DAY)
        with pytest.raises(Refused) as caught:
            pending.approve("bob", DAY)
        assert "already approved" in str(caught.value)

    def test_two_distinct_approvers_complete_it(self):
        pending = _pending("50000.00")
        pending.submit()
        pending.approve("bob", DAY)
        assert pending.approve("carol", DAY) is ApprovalState.APPROVED

    def test_outstanding_approvals_count_down(self):
        pending = _pending("50000.00")
        pending.submit()
        assert pending.outstanding_approvals() == 2
        pending.approve("bob", DAY)
        assert pending.outstanding_approvals() == 1


class TestPosting:
    def test_an_approved_entry_posts(self):
        ledger = _ledger()
        pending = _pending("500.00")
        pending.submit()
        pending.approve("bob", DAY)
        pending.post(ledger)
        assert ledger.entry_count() == 1
        assert pending.state is ApprovalState.POSTED

    def test_a_pending_entry_cannot_post(self):
        ledger = _ledger()
        pending = _pending("500.00")
        pending.submit()
        with pytest.raises(Refused) as caught:
            pending.post(ledger)
        assert "approval is outstanding" in str(caught.value)

    def test_a_rejected_entry_cannot_post(self):
        ledger = _ledger()
        pending = _pending("500.00")
        pending.submit()
        pending.reject("bob", "the coding looks wrong")
        with pytest.raises(Refused):
            pending.post(ledger)


class TestRejection:
    def test_a_rejection_records_who_and_why(self):
        pending = _pending("500.00")
        pending.submit()
        pending.reject("bob", "wrong account")
        assert pending.rejected_by == "bob"
        assert pending.rejection_reason == "wrong account"

    def test_a_rejection_needs_a_reason(self):
        pending = _pending("500.00")
        pending.submit()
        with pytest.raises(Refused) as caught:
            pending.reject("bob", "  ")
        assert "nobody can learn from" in str(caught.value)

    def test_a_rejection_needs_a_rejector(self):
        pending = _pending("500.00")
        pending.submit()
        with pytest.raises(Refused):
            pending.reject("  ", "wrong account")

    def test_submitting_twice_is_refused(self):
        pending = _pending("500.00")
        pending.submit()
        with pytest.raises(Refused):
            pending.submit()
