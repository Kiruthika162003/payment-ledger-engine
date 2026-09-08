"""Dunning: the ladder of reminders, escalating only when a step is actually due.

Chasing an overdue invoice is a sequence of increasingly firm
contacts, and the whole discipline is in not skipping steps and not
repeating them. A customer who receives the friendly reminder twice
learns the system is noise; one who receives the final notice first
learns the supplier is hostile. This module models the ladder as
ordered steps, each with the days-overdue threshold at which it
becomes due, and asks one question: given how overdue this invoice
is and which steps have already been sent, what is the next step to
send now. It returns nothing when the invoice is not yet overdue
enough for the next rung, which is the answer that keeps a nightly
job from spamming, and it never returns a step already sent. When
an invoice has sat long enough to pass several thresholds at once,
the ladder advances one rung rather than jumping to the end, on the
principle that a customer should see the escalation rather than
have it happen to them. Steps must have strictly increasing
thresholds, since a ladder whose rungs are out of order has no
defined next step.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mint.errors import Refused


@dataclass(frozen=True)
class DunningStep:
    name: str
    days_overdue: int
    message: str


@dataclass
class DunningLadder:
    steps: tuple[DunningStep, ...]
    sent: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.steps:
            raise Refused("a dunning ladder needs at least one step")
        thresholds = [step.days_overdue for step in self.steps]
        if thresholds != sorted(thresholds) or len(set(thresholds)) != len(thresholds):
            raise Refused(
                "dunning steps must have strictly increasing thresholds; a "
                "ladder whose rungs are out of order has no defined next step"
            )
        if thresholds[0] < 0:
            raise Refused("a dunning step triggers at zero days overdue or later")

    def next_step(self, days_overdue: int) -> DunningStep | None:
        for step in self.steps:
            if step.name in self.sent:
                continue
            if days_overdue >= step.days_overdue:
                return step
            return None
        return None

    def send(self, days_overdue: int) -> DunningStep | None:
        step = self.next_step(days_overdue)
        if step is not None:
            self.sent.append(step.name)
        return step

    def is_exhausted(self) -> bool:
        return len(self.sent) == len(self.steps)

    def remaining(self) -> tuple[DunningStep, ...]:
        return tuple(step for step in self.steps if step.name not in self.sent)


def standard_ladder() -> DunningLadder:
    return DunningLadder(
        steps=(
            DunningStep("reminder", 1, "A friendly note that the invoice is past due."),
            DunningStep("second notice", 15, "A firmer request for payment."),
            DunningStep("final notice", 45, "Payment is required to avoid escalation."),
            DunningStep("collections", 75, "The account is referred for collection."),
        )
    )
