"""Milestone billing: invoicing a project in stages, and never past the contract.

A project billed in milestones invoices a share of the contract as
each stage completes, and the constraints are simple to state and
easy to violate: the milestones must sum to the contract, no
milestone bills before it is accepted, and the total invoiced can
never exceed the contract however the stages are rearranged. This
module holds those constraints. Milestone shares are given as
weights and converted to amounts with the cent conserved, so the
stages add back to the contract exactly rather than leaving a
rounding stub that either gets billed as a mysterious extra line or
never gets billed at all. A retention percentage is supported, the
slice a client withholds from each invoice until the whole project
is accepted, which is standard in construction and is the thing
most billing code forgets: the retained amount is still owed, it is
simply not yet payable, so the module reports invoiced, retained,
and payable separately rather than collapsing them into one figure
that misstates both what the client owes and what the contractor
can collect today.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, allocate, scale


@dataclass
class Milestone:
    name: str
    weight: int
    amount: Money
    accepted_on: datetime.date | None = None
    invoiced: bool = False

    def is_accepted(self) -> bool:
        return self.accepted_on is not None


@dataclass
class MilestoneContract:
    id: str
    contract_value: Money
    retention_rate: Fraction = Fraction(0)
    milestones: list[Milestone] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.contract_value.is_positive():
            raise Refused("a contract has a positive value")
        if self.retention_rate < 0 or self.retention_rate >= 1:
            raise Refused("a retention rate is a fraction below one")

    def define(self, names_and_weights: list[tuple[str, int]]) -> list[Milestone]:
        if not names_and_weights:
            raise Refused("a contract needs at least one milestone")
        if any(weight < 1 for _, weight in names_and_weights):
            raise Refused("every milestone carries a positive weight")
        shares = allocate(
            self.contract_value, [Fraction(w) for _, w in names_and_weights]
        )
        self.milestones = [
            Milestone(name=name, weight=weight, amount=amount)
            for (name, weight), amount in zip(names_and_weights, shares, strict=True)
        ]
        return self.milestones

    def get(self, name: str) -> Milestone:
        for milestone in self.milestones:
            if milestone.name == name:
                return milestone
        raise Refused(f"contract {self.id!r} has no milestone {name!r}")

    def milestones_sum_to_contract(self) -> bool:
        total = Money.zero(self.contract_value.currency)
        for milestone in self.milestones:
            total = total + milestone.amount
        return total == self.contract_value

    def accept(self, name: str, on: datetime.date) -> Milestone:
        milestone = self.get(name)
        if milestone.is_accepted():
            raise Refused(f"milestone {name!r} was already accepted")
        milestone.accepted_on = on
        return milestone

    def invoice(self, name: str) -> Money:
        milestone = self.get(name)
        if not milestone.is_accepted():
            raise Refused(
                f"milestone {name!r} has not been accepted; a stage bills after "
                "it is accepted, not before"
            )
        if milestone.invoiced:
            raise Refused(f"milestone {name!r} has already been invoiced")
        milestone.invoiced = True
        return milestone.amount

    def invoiced_total(self) -> Money:
        total = Money.zero(self.contract_value.currency)
        for milestone in self.milestones:
            if milestone.invoiced:
                total = total + milestone.amount
        return total

    def retained_total(self) -> Money:
        return scale(self.invoiced_total(), self.retention_rate, Rounding.HALF_EVEN)

    def payable_now(self) -> Money:
        return self.invoiced_total() - self.retained_total()

    def is_complete(self) -> bool:
        return all(milestone.invoiced for milestone in self.milestones)

    def release_retention(self) -> Money:
        if not self.is_complete():
            raise Refused(
                f"contract {self.id!r} is not fully invoiced; retention is "
                "released when the project is accepted, not before"
            )
        return self.retained_total()

    def never_exceeds_contract(self) -> bool:
        return self.invoiced_total() <= self.contract_value
