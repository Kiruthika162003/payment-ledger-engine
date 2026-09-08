"""A subscription's life: trial, active, past due, cancelled, and the way back.

Subscription billing is a state machine, and revenue leaks at the
transitions rather than in the states. A trial that converts must
start billing on the right day; a failed payment must move the
subscription to past due rather than cancelling it, because most
failed payments are a expired card and cancelling immediately loses
a customer who would have paid; a past due subscription must
eventually cancel rather than accruing forever, since a service
given away indefinitely to someone who stopped paying is not a
retention strategy. This module makes those transitions explicit
and refuses the illegal ones. Cancellation distinguishes immediate
from end-of-period, which is the difference between a refund and
none, and reactivation is allowed from cancelled but starts a new
period rather than resuming the old one, because resuming a period
the customer did not pay for gives away the time between. Every
transition records its date, so the billing history can be
reconstructed rather than trusted.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.calendarutil import add_months
from mint.errors import Refused
from mint.money import Money
from mint.subscription import prorated_charge


class State(Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Transition:
    at: datetime.date
    from_state: State
    to_state: State
    reason: str


_ALLOWED: dict[State, frozenset[State]] = {
    State.TRIALING: frozenset({State.ACTIVE, State.CANCELLED}),
    State.ACTIVE: frozenset({State.PAST_DUE, State.CANCELLED}),
    State.PAST_DUE: frozenset({State.ACTIVE, State.CANCELLED}),
    State.CANCELLED: frozenset({State.ACTIVE}),
}


@dataclass
class Subscription:
    id: str
    price: Money
    started: datetime.date
    state: State = State.TRIALING
    period_start: datetime.date | None = None
    period_end: datetime.date | None = None
    failed_attempts: int = 0
    max_attempts: int = 4
    cancel_at_period_end: bool = False
    history: list[Transition] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.price.is_positive():
            raise Refused("a subscription has a positive price")
        if self.period_start is None:
            self.period_start = self.started
        if self.period_end is None:
            self.period_end = add_months(self.started, 1)

    def _move(self, to_state: State, on: datetime.date, reason: str) -> State:
        if to_state not in _ALLOWED[self.state]:
            raise Refused(
                f"subscription {self.id!r} cannot move from {self.state.value} "
                f"to {to_state.value}"
            )
        self.history.append(Transition(on, self.state, to_state, reason))
        self.state = to_state
        return self.state

    def convert(self, on: datetime.date) -> State:
        if self.state is not State.TRIALING:
            raise Refused(f"subscription {self.id!r} is not on trial")
        self.period_start = on
        self.period_end = add_months(on, 1)
        return self._move(State.ACTIVE, on, "trial converted")

    def payment_failed(self, on: datetime.date) -> State:
        if self.state not in (State.ACTIVE, State.PAST_DUE):
            raise Refused(
                f"subscription {self.id!r} is {self.state.value} and is not "
                "being billed"
            )
        self.failed_attempts += 1
        if self.failed_attempts >= self.max_attempts:
            # Eventually it must cancel: a service given away indefinitely to
            # someone who stopped paying is not a retention strategy.
            return self._move(State.CANCELLED, on, "payment retries exhausted")
        if self.state is State.ACTIVE:
            return self._move(State.PAST_DUE, on, "payment failed")
        return self.state

    def payment_succeeded(self, on: datetime.date) -> State:
        if self.state not in (State.ACTIVE, State.PAST_DUE):
            raise Refused(f"subscription {self.id!r} is {self.state.value}")
        self.failed_attempts = 0
        self.period_start = on
        self.period_end = add_months(on, 1)
        if self.state is State.PAST_DUE:
            return self._move(State.ACTIVE, on, "payment recovered")
        return self.state

    def cancel(self, on: datetime.date, immediately: bool = True) -> State:
        if self.state is State.CANCELLED:
            raise Refused(f"subscription {self.id!r} is already cancelled")
        if not immediately:
            self.cancel_at_period_end = True
            return self.state
        return self._move(State.CANCELLED, on, "cancelled")

    def refund_due(self, on: datetime.date) -> Money:
        # Only an immediate cancellation refunds the unused slice.
        if self.state is not State.CANCELLED:
            return Money.zero(self.price.currency)
        if not (self.period_start <= on <= self.period_end):
            return Money.zero(self.price.currency)
        return prorated_charge(self.price, on, self.period_start, self.period_end)

    def reactivate(self, on: datetime.date) -> State:
        if self.state is not State.CANCELLED:
            raise Refused(f"subscription {self.id!r} is not cancelled")
        # A new period, not a resumed one: resuming would give away the gap.
        self.period_start = on
        self.period_end = add_months(on, 1)
        self.failed_attempts = 0
        self.cancel_at_period_end = False
        return self._move(State.ACTIVE, on, "reactivated")

    def is_billable(self) -> bool:
        return self.state in (State.ACTIVE, State.PAST_DUE)

    def days_past_due(self, as_of: datetime.date) -> int:
        if self.state is not State.PAST_DUE:
            return 0
        return max(0, (as_of - self.period_end).days)
