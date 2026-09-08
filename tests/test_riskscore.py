from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.riskscore import Decision, RiskFactor, RiskModel


def _model() -> RiskModel:
    model = RiskModel(review_at=30, decline_at=70)
    model.add(RiskFactor("new account", 40, lambda t: t["age_days"] < 7))
    model.add(RiskFactor("large amount", 35, lambda t: t["amount"] > 1000))
    model.add(RiskFactor("known good", -25, lambda t: t.get("trusted", False)))
    return model


def _txn(**kwargs):
    base = {"age_days": 400, "amount": 50, "trusted": False}
    base.update(kwargs)
    return base


class TestScoring:
    def test_a_clean_transaction_approves(self):
        result = _model().assess(_txn())
        assert result.score == 0
        assert result.decision is Decision.APPROVE

    def test_one_signal_sends_it_to_review(self):
        result = _model().assess(_txn(age_days=1))
        assert result.score == 40
        assert result.decision is Decision.REVIEW

    def test_two_signals_decline(self):
        result = _model().assess(_txn(age_days=1, amount=5000))
        assert result.score == 75
        assert result.decision is Decision.DECLINE

    def test_a_negative_factor_offsets(self):
        result = _model().assess(_txn(age_days=1, amount=5000, trusted=True))
        assert result.score == 50
        assert result.decision is Decision.REVIEW


class TestExplanation:
    def test_the_contributing_factors_are_named(self):
        result = _model().assess(_txn(age_days=1, amount=5000))
        names = {name for name, _ in result.contributions}
        assert names == {"new account", "large amount"}

    def test_the_explanation_is_ordered_by_impact(self):
        result = _model().assess(_txn(age_days=1, amount=5000))
        assert result.explain()[0].startswith("new account")

    def test_the_top_factor_is_reported(self):
        result = _model().assess(_txn(age_days=1, amount=5000))
        assert result.top_factor() == "new account"

    def test_a_clean_assessment_has_no_top_factor(self):
        assert _model().assess(_txn()).top_factor() is None


class TestThresholds:
    def test_the_boundary_is_inclusive(self):
        model = _model()
        assert model.decide(30) is Decision.REVIEW
        assert model.decide(29) is Decision.APPROVE
        assert model.decide(70) is Decision.DECLINE

    def test_inverted_thresholds_are_refused(self):
        with pytest.raises(Refused) as caught:
            RiskModel(review_at=70, decline_at=30)
        assert "already declined" in str(caught.value)

    def test_a_duplicate_factor_is_refused(self):
        model = _model()
        with pytest.raises(Refused):
            model.add(RiskFactor("new account", 10, lambda _t: True))
