from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.expensereport import Claim, ExpensePolicy, ExpenseReport
from mint.money import Money

START = datetime.date(2026, 3, 1)
END = datetime.date(2026, 3, 31)
IN_PERIOD = datetime.date(2026, 3, 15)
OUTSIDE = datetime.date(2026, 1, 5)


def _policy() -> ExpensePolicy:
    policy = ExpensePolicy(currency="USD", receipt_threshold=Money.of(25, "USD"))
    policy.set_cap("meals", Money.of(60, "USD"))
    policy.set_cap("hotel", Money.of(300, "USD"))
    return policy


def _report() -> ExpenseReport:
    return ExpenseReport("ER-1", "alice", START, END, _policy())


class TestCleanClaims:
    def test_a_compliant_claim_passes(self):
        report = _report()
        report.add(Claim("c1", "meals", Money.of(20, "USD"), IN_PERIOD))
        assert report.is_clean()
        assert report.reimbursable() == Money.of(20, "USD")

    def test_a_receipted_large_claim_passes(self):
        report = _report()
        report.add(
            Claim("c1", "hotel", Money.of(200, "USD"), IN_PERIOD, has_receipt=True)
        )
        assert report.is_clean()


class TestViolations:
    def test_a_claim_over_the_cap_is_flagged(self):
        report = _report()
        report.add(
            Claim("c1", "meals", Money.of(90, "USD"), IN_PERIOD, has_receipt=True)
        )
        assert [v.rule for v in report.violations()] == ["category cap"]

    def test_a_missing_receipt_is_flagged(self):
        report = _report()
        report.add(Claim("c1", "meals", Money.of(40, "USD"), IN_PERIOD))
        assert [v.rule for v in report.violations()] == ["receipt required"]

    def test_a_claim_outside_the_period_is_flagged(self):
        report = _report()
        report.add(Claim("c1", "meals", Money.of(10, "USD"), OUTSIDE))
        assert [v.rule for v in report.violations()] == ["outside the period"]

    def test_violations_name_their_claim(self):
        report = _report()
        report.add(Claim("c1", "meals", Money.of(10, "USD"), IN_PERIOD))
        report.add(Claim("c2", "meals", Money.of(90, "USD"), IN_PERIOD, has_receipt=True))
        assert {v.claim_id for v in report.violations()} == {"c2"}

    def test_a_flagged_claim_is_not_reimbursed(self):
        report = _report()
        report.add(Claim("c1", "meals", Money.of(10, "USD"), IN_PERIOD))
        report.add(Claim("c2", "meals", Money.of(90, "USD"), IN_PERIOD, has_receipt=True))
        assert report.reimbursable() == Money.of(10, "USD")
        assert report.submitted_total() == Money.of(100, "USD")


class TestOverrides:
    def test_an_override_clears_the_violation(self):
        report = _report()
        report.add(Claim("c1", "meals", Money.of(90, "USD"), IN_PERIOD, has_receipt=True))
        report.override("c1", "manager", "client dinner approved in advance")
        assert report.is_clean()
        assert report.reimbursable() == Money.of(90, "USD")

    def test_an_override_records_who_and_why(self):
        report = _report()
        report.add(Claim("c1", "meals", Money.of(90, "USD"), IN_PERIOD, has_receipt=True))
        note = report.override("c1", "manager", "client dinner")
        assert "manager" in note and "client dinner" in note

    def test_an_override_needs_a_reason(self):
        report = _report()
        report.add(Claim("c1", "meals", Money.of(90, "USD"), IN_PERIOD, has_receipt=True))
        with pytest.raises(Refused) as caught:
            report.override("c1", "manager", "  ")
        assert "exceptions exist to be visible" in str(caught.value)

    def test_overriding_an_unknown_claim_is_refused(self):
        with pytest.raises(Refused):
            _report().override("ghost", "manager", "reason")


class TestApproval:
    def test_a_clean_report_approves(self):
        report = _report()
        report.add(Claim("c1", "meals", Money.of(20, "USD"), IN_PERIOD))
        assert report.approve("manager") == "manager"

    def test_a_dirty_report_cannot_be_approved(self):
        report = _report()
        report.add(Claim("c1", "meals", Money.of(90, "USD"), IN_PERIOD, has_receipt=True))
        with pytest.raises(Refused) as caught:
            report.approve("manager")
        assert "unresolved" in str(caught.value)

    def test_a_duplicate_claim_id_is_refused(self):
        report = _report()
        report.add(Claim("c1", "meals", Money.of(20, "USD"), IN_PERIOD))
        with pytest.raises(Refused):
            report.add(Claim("c1", "meals", Money.of(20, "USD"), IN_PERIOD))
