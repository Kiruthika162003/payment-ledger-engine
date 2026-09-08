"""Escrow: money held by neither party until the condition both agreed on is met.

Escrow exists because two parties who do not trust each other still
want to trade, so a third party holds the money until the agreed
condition is satisfied. The ledger consequence is that escrowed
funds belong to neither the payer nor the payee while they sit
there, and booking them as either party's asset misstates both
balance sheets. This module models the arrangement as a small state
machine with the states that actually occur: funded, released to the
payee, refunded to the payer, or disputed and awaiting a decision.
Release and refund are both terminal and mutually exclusive, since
money released to the seller cannot also go back to the buyer, and
the module refuses the second of any such pair rather than paying
twice. Partial release is supported, because milestone work is
usually paid in stages, and the remainder stays escrowed with the
arrangement still open. An escrow can only be released by an agent
authorized on it, which is the whole point of the third party: a
release the payer can perform alone is not escrow, it is a delay.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.errors import Refused
from mint.money import Money


class EscrowState(Enum):
    FUNDED = "funded"
    PARTIALLY_RELEASED = "partially_released"
    RELEASED = "released"
    REFUNDED = "refunded"
    DISPUTED = "disputed"


@dataclass(frozen=True)
class EscrowMovement:
    date: datetime.date
    amount: Money
    direction: str
    by: str


@dataclass
class Escrow:
    id: str
    payer: str
    payee: str
    amount: Money
    funded_on: datetime.date
    agents: frozenset[str]
    movements: list[EscrowMovement] = field(default_factory=list)
    disputed: bool = False
    refunded: bool = False

    def __post_init__(self) -> None:
        if not self.amount.is_positive():
            raise Refused("an escrow holds a positive amount")
        if not self.agents:
            raise Refused(
                "an escrow needs at least one authorized agent; a release the "
                "payer can perform alone is not escrow, it is a delay"
            )

    def released_total(self) -> Money:
        total = Money.zero(self.amount.currency)
        for movement in self.movements:
            if movement.direction == "release":
                total = total + movement.amount
        return total

    def refunded_total(self) -> Money:
        total = Money.zero(self.amount.currency)
        for movement in self.movements:
            if movement.direction == "refund":
                total = total + movement.amount
        return total

    def held(self) -> Money:
        return self.amount - self.released_total() - self.refunded_total()

    def state(self) -> EscrowState:
        if self.refunded:
            return EscrowState.REFUNDED
        if self.disputed:
            return EscrowState.DISPUTED
        if self.held().is_zero():
            return EscrowState.RELEASED
        if self.released_total().is_positive():
            return EscrowState.PARTIALLY_RELEASED
        return EscrowState.FUNDED

    def _guard(self, amount: Money, agent: str, verb: str) -> None:
        amount.same_currency(self.amount)
        if agent not in self.agents:
            raise Refused(
                f"{agent!r} is not authorized on escrow {self.id!r} and cannot "
                f"{verb} it"
            )
        if self.refunded:
            raise Refused(f"escrow {self.id!r} was refunded and is closed")
        if not amount.is_positive():
            raise Refused("an escrow movement carries a positive amount")
        if amount > self.held():
            raise Refused(
                f"a {verb} of {amount.format()} exceeds the "
                f"{self.held().format()} still held in escrow {self.id!r}"
            )

    def release(self, amount: Money, on: datetime.date, agent: str) -> Money:
        self._guard(amount, agent, "release")
        if self.disputed:
            raise Refused(
                f"escrow {self.id!r} is disputed; resolve the dispute before "
                "releasing"
            )
        self.movements.append(EscrowMovement(on, amount, "release", agent))
        return self.held()

    def refund(self, on: datetime.date, agent: str) -> Money:
        remaining = self.held()
        self._guard(remaining, agent, "refund")
        self.movements.append(EscrowMovement(on, remaining, "refund", agent))
        self.refunded = True
        return remaining

    def dispute(self, by: str) -> EscrowState:
        if by not in (self.payer, self.payee):
            raise Refused("only the payer or the payee may dispute an escrow")
        if self.held().is_zero():
            raise Refused(f"escrow {self.id!r} holds nothing left to dispute")
        self.disputed = True
        return self.state()

    def resolve(self, agent: str) -> EscrowState:
        if agent not in self.agents:
            raise Refused(f"{agent!r} is not authorized to resolve this escrow")
        self.disputed = False
        return self.state()
