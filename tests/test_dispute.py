from __future__ import annotations

import datetime

import pytest

from mint.dispute import Dispute, DisputeStatus
from mint.errors import Refused
from mint.money import Money

DAY = datetime.date(2026, 4, 1)


def _dispute(amount: str = "50.00", charge: str = "100.00") -> Dispute:
    return Dispute("dp_1", "ch_1", Money.of(amount, "USD"), DAY, Money.of(charge, "USD"))


class TestConstruction:
    def test_a_dispute_cannot_exceed_the_charge(self):
        with pytest.raises(Refused) as caught:
            _dispute(amount="150.00", charge="100.00")
        assert "cannot claw back more" in str(caught.value)

    def test_a_fresh_dispute_is_open(self):
        assert _dispute().is_open()
        assert _dispute().status is DisputeStatus.OPEN


class TestLifecycle:
    def test_evidence_moves_it_under_review(self):
        dispute = _dispute()
        dispute.submit_evidence("shipping proof", DAY)
        assert dispute.status is DisputeStatus.UNDER_REVIEW

    def test_a_win_returns_the_funds_to_the_merchant(self):
        dispute = _dispute()
        dispute.submit_evidence("proof", DAY)
        dispute.resolve(won=True, on=DAY)
        assert dispute.merchant_keeps_funds()
        assert dispute.funds_reversed().is_zero()

    def test_a_loss_reverses_the_amount(self):
        dispute = _dispute()
        dispute.resolve(won=False, on=DAY)
        assert dispute.funds_reversed() == Money.of(50, "USD")

    def test_accepting_concedes_the_amount(self):
        dispute = _dispute()
        conceded = dispute.accept(DAY)
        assert conceded == Money.of(50, "USD")
        assert dispute.status is DisputeStatus.ACCEPTED
        assert dispute.funds_reversed() == Money.of(50, "USD")


class TestTerminal:
    def test_resolving_twice_is_refused(self):
        dispute = _dispute()
        dispute.resolve(won=True, on=DAY)
        with pytest.raises(Refused) as caught:
            dispute.resolve(won=False, on=DAY)
        assert "terminal state is final" in str(caught.value)

    def test_evidence_after_resolution_is_refused(self):
        dispute = _dispute()
        dispute.accept(DAY)
        with pytest.raises(Refused):
            dispute.submit_evidence("too late", DAY)
