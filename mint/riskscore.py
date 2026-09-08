"""Risk scoring: a number a human can argue with, because it shows its reasons.

A risk score that arrives as a bare number is useless to the person
who has to act on it, because they cannot tell a genuinely risky
transaction from one that tripped a badly calibrated rule. This
module builds scores from named factors, each contributing a stated
weight when its condition holds, and returns the contributing
factors alongside the total, so a decline can be explained to a
customer and a rule that fires on everything can be found and
fixed. Weights are integers rather than probabilities, because
calling a weighted sum of heuristics a probability implies a
calibration nobody performed, and the honest presentation is a
score with a threshold rather than a percentage that invites false
precision. The thresholds are named bands, approve, review, and
decline, so the policy lives in one visible place instead of being
scattered as magic numbers through the code that calls it. A
factor's weight may be negative, since some signals genuinely
reduce risk, and a long-standing customer with a clean history
should be able to offset a signal that would flag a stranger.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mint.errors import Refused


class Decision(Enum):
    APPROVE = "approve"
    REVIEW = "review"
    DECLINE = "decline"


@dataclass(frozen=True)
class RiskFactor:
    name: str
    weight: int
    condition: Callable[[Any], bool]
    explanation: str = ""


@dataclass(frozen=True)
class RiskAssessment:
    score: int
    contributions: tuple[tuple[str, int], ...]
    decision: Decision

    def explain(self) -> list[str]:
        return [
            f"{name}: {weight:+d}"
            for name, weight in sorted(
                self.contributions, key=lambda item: -abs(item[1])
            )
        ]

    def top_factor(self) -> str | None:
        if not self.contributions:
            return None
        return max(self.contributions, key=lambda item: abs(item[1]))[0]


@dataclass
class RiskModel:
    review_at: int
    decline_at: int
    factors: list[RiskFactor] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.decline_at <= self.review_at:
            raise Refused(
                "the decline threshold must sit above the review threshold, or "
                "every reviewable transaction is already declined"
            )

    def add(self, factor: RiskFactor) -> RiskFactor:
        if any(existing.name == factor.name for existing in self.factors):
            raise Refused(f"a factor named {factor.name!r} is already in the model")
        self.factors.append(factor)
        return factor

    def assess(self, subject: Any) -> RiskAssessment:
        contributions: list[tuple[str, int]] = []
        score = 0
        for factor in self.factors:
            if factor.condition(subject):
                contributions.append((factor.name, factor.weight))
                score += factor.weight
        return RiskAssessment(
            score=score,
            contributions=tuple(contributions),
            decision=self.decide(score),
        )

    def decide(self, score: int) -> Decision:
        if score >= self.decline_at:
            return Decision.DECLINE
        if score >= self.review_at:
            return Decision.REVIEW
        return Decision.APPROVE
