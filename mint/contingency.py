"""Contingencies: provide, disclose, or say nothing, decided by likelihood.

A lawsuit that might cost money is not yet a cost, and accounting
draws two lines through the uncertainty rather than one. If an
outflow is probable and can be estimated, it is provided for and
hits profit now. If it is only possible, it is disclosed in a note
but not provided, because providing for everything that might
happen would make every set of accounts a work of fiction. If it is
remote, nothing is said at all. This module encodes those three
outcomes and refuses to blur them, since the most common error is
providing for a possible obligation, which understates profit and
creates a reserve that can be quietly released later to flatter a
bad year, an abuse well known enough to have a name. When the
estimate is a range rather than a number, the convention taken here
is the midpoint when no point in the range is more likely, and the
module says which convention it used rather than presenting a
single number as though it were certain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from mint.errors import Refused
from mint.money import Money


class Likelihood(Enum):
    PROBABLE = "probable"
    POSSIBLE = "possible"
    REMOTE = "remote"


class Treatment(Enum):
    PROVIDE = "provide"
    DISCLOSE = "disclose"
    IGNORE = "ignore"


@dataclass(frozen=True)
class Estimate:
    low: Money
    high: Money

    def __post_init__(self) -> None:
        self.high.same_currency(self.low)
        if self.high < self.low:
            raise Refused("an estimate range runs from low to high")
        if self.low.is_negative():
            raise Refused("an estimated outflow is not negative")

    def is_point(self) -> bool:
        return self.low == self.high

    def midpoint(self) -> Money:
        return Money.from_minor(
            (self.low.units + self.high.units) // 2, self.low.currency
        )

    def best_estimate(self) -> tuple[Money, str]:
        # The convention is named rather than a single number presented as
        # though it were certain.
        if self.is_point():
            return self.low, "a single estimate"
        return self.midpoint(), "the midpoint, no point in the range being more likely"


@dataclass
class Contingency:
    id: str
    description: str
    likelihood: Likelihood
    estimate: Estimate | None = None
    provided: Money | None = None

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise Refused("a contingency needs a description")
        if self.estimate is not None and self.provided is None:
            self.provided = Money.zero(self.estimate.low.currency)

    def is_estimable(self) -> bool:
        return self.estimate is not None

    def treatment(self) -> Treatment:
        if self.likelihood is Likelihood.REMOTE:
            return Treatment.IGNORE
        if self.likelihood is Likelihood.PROBABLE and self.is_estimable():
            return Treatment.PROVIDE
        # Probable but inestimable is disclosed, not provided at a guess.
        return Treatment.DISCLOSE

    def required_provision(self) -> Money:
        if self.treatment() is not Treatment.PROVIDE:
            if self.estimate is None:
                raise Refused(
                    f"contingency {self.id!r} has no estimate to provide from"
                )
            return Money.zero(self.estimate.low.currency)
        return self.estimate.best_estimate()[0]

    def movement(self) -> Money:
        return self.required_provision() - self.provided

    def post(self) -> Money:
        movement = self.movement()
        self.provided = self.required_provision()
        return movement

    def reassess(self, likelihood: Likelihood) -> Treatment:
        self.likelihood = likelihood
        return self.treatment()

    def disclosure(self) -> str | None:
        if self.treatment() is Treatment.IGNORE:
            return None
        if self.treatment() is Treatment.PROVIDE:
            amount, basis = self.estimate.best_estimate()
            return f"{self.description}: provided at {amount.format()} on {basis}"
        if self.estimate is None:
            return f"{self.description}: possible, but no reliable estimate exists"
        return (
            f"{self.description}: possible, estimated between "
            f"{self.estimate.low.format()} and {self.estimate.high.format()}"
        )


@dataclass
class ContingencyRegister:
    currency: str
    items: list[Contingency] = field(default_factory=list)

    def add(self, item: Contingency) -> Contingency:
        if any(existing.id == item.id for existing in self.items):
            raise Refused(f"contingency {item.id!r} is already registered")
        self.items.append(item)
        return item

    def total_provided(self) -> Money:
        total = Money.zero(self.currency)
        for item in self.items:
            if item.treatment() is Treatment.PROVIDE:
                total = total + item.required_provision()
        return total

    def disclosed_only(self) -> list[Contingency]:
        return [item for item in self.items if item.treatment() is Treatment.DISCLOSE]

    def notes(self) -> list[str]:
        return [item.disclosure() for item in self.items if item.disclosure()]

    def maximum_exposure(self) -> Money:
        total = Money.zero(self.currency)
        for item in self.items:
            if item.estimate is not None and item.treatment() is not Treatment.IGNORE:
                total = total + item.estimate.high
        return total
