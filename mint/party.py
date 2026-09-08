"""Parties: the customers and vendors money moves to and from.

A ledger of accounts alone cannot answer the question a business
asks most often, which is not what the receivables balance is but
who owes it. Parties are the customers and vendors behind the
postings, and this module keeps the registry and the running
balance for each. A party has a role, since the same organization
can be both a customer and a vendor and netting the two without
saying so is how a supplier's unpaid bill silently offsets their
unpaid invoice; the registry keeps the roles distinct and offers
the net position as a separate question with an explicit answer. A
party holds one currency for its balance, because a customer who
trades in two currencies has two positions and averaging them
produces a number no collector can act on. Balances move by charges
and payments rather than being set, so the balance is always the
sum of what happened, and a payment larger than the outstanding
balance is refused with the overpayment named, since a credit
balance on a customer is a real thing that should be created
deliberately rather than by a typo in a payment amount.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.errors import Refused
from mint.money import Money


class PartyRole(Enum):
    CUSTOMER = "customer"
    VENDOR = "vendor"
    BOTH = "both"


@dataclass(frozen=True)
class PartyMovement:
    date: datetime.date
    amount: Money
    memo: str


@dataclass
class Party:
    id: str
    name: str
    role: PartyRole
    currency: str
    movements: list[PartyMovement] = field(default_factory=list)

    def balance(self) -> Money:
        total = Money.zero(self.currency)
        for movement in self.movements:
            total = total + movement.amount
        return total

    def _guard(self, amount: Money) -> None:
        if amount.currency != self.currency:
            raise Refused(
                f"party {self.id!r} trades in {self.currency}; a "
                f"{amount.currency} position is a separate one"
            )
        if not amount.is_positive():
            raise Refused("a party movement carries a positive amount")

    def charge(self, amount: Money, on: datetime.date, memo: str = "invoice") -> Money:
        self._guard(amount)
        self.movements.append(PartyMovement(on, amount, memo))
        return self.balance()

    def credit(self, amount: Money, on: datetime.date, memo: str = "payment") -> Money:
        self._guard(amount)
        if amount > self.balance():
            raise Refused(
                f"a credit of {amount.format()} exceeds the "
                f"{self.balance().format()} owed by {self.id!r}; an overpayment "
                "should be recorded deliberately, not by a typo"
            )
        self.movements.append(PartyMovement(on, -amount, memo))
        return self.balance()

    def is_settled(self) -> bool:
        return self.balance().is_zero()


@dataclass
class PartyRegistry:
    parties: dict[str, Party] = field(default_factory=dict)

    def add(self, party: Party) -> Party:
        if party.id in self.parties:
            raise Refused(f"party {party.id!r} is already registered")
        self.parties[party.id] = party
        return party

    def get(self, party_id: str) -> Party:
        if party_id not in self.parties:
            raise Refused(f"there is no party {party_id!r} in the registry")
        return self.parties[party_id]

    def of_role(self, role: PartyRole) -> list[Party]:
        return sorted(
            (
                party
                for party in self.parties.values()
                if party.role is role or party.role is PartyRole.BOTH
            ),
            key=lambda p: p.id,
        )

    def total_owed(self, role: PartyRole, currency: str) -> Money:
        total = Money.zero(currency)
        for party in self.of_role(role):
            if party.currency == currency:
                total = total + party.balance()
        return total

    def net_position(self, party_id: str, other: PartyRegistry) -> Money:
        # Netting a customer balance against a vendor balance is an explicit
        # request, never an accident of storing both in one place.
        mine = self.get(party_id)
        theirs = other.get(party_id)
        return mine.balance() - theirs.balance()
