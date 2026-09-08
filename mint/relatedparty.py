"""Related parties: transactions that need naming because the price may not be real.

A sale to an unrelated customer is priced by a negotiation between
two people who each want the better end of it, and that is what
makes the number meaningful. A sale to the chief executive's own
company is not, and the reader of the accounts has no way to tell
the two apart unless they are disclosed. This module keeps the
register of related parties and the transactions with them, and
answers the question disclosure rules actually ask: which of these
are individually or collectively material enough to name. The
relationship is what makes a party related, not the size of the
transaction, so a tiny transaction with a director is still a
related-party transaction and a huge one with a stranger is not,
which is the confusion the module refuses to make. Outstanding
balances are tracked separately from transactions in the period,
since a related party who bought a great deal and paid promptly
poses a different question from one who bought a little and never
paid.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money


class Relationship(Enum):
    DIRECTOR = "director"
    KEY_MANAGEMENT = "key_management"
    PARENT = "parent"
    SUBSIDIARY = "subsidiary"
    ASSOCIATE = "associate"
    CLOSE_FAMILY = "close_family"
    ENTITY_CONTROLLED = "entity_controlled_by_a_related_party"


@dataclass(frozen=True)
class RelatedParty:
    id: str
    name: str
    relationship: Relationship

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise Refused("a related party needs a name")


@dataclass(frozen=True)
class RelatedTransaction:
    party_id: str
    date: datetime.date
    amount: Money
    description: str
    outstanding: Money | None = None

    def __post_init__(self) -> None:
        if not self.amount.is_positive():
            raise Refused("a related-party transaction is for a positive amount")
        if self.outstanding is not None:
            self.outstanding.same_currency(self.amount)
            if self.outstanding > self.amount:
                raise Refused("more is outstanding than was ever transacted")


@dataclass
class RelatedPartyRegister:
    currency: str
    parties: dict[str, RelatedParty] = field(default_factory=dict)
    transactions: list[RelatedTransaction] = field(default_factory=list)

    def register(self, party: RelatedParty) -> RelatedParty:
        if party.id in self.parties:
            raise Refused(f"party {party.id!r} is already registered")
        self.parties[party.id] = party
        return party

    def is_related(self, party_id: str) -> bool:
        # The relationship makes a party related, never the size of the deal.
        return party_id in self.parties

    def record(self, transaction: RelatedTransaction) -> RelatedTransaction:
        if not self.is_related(transaction.party_id):
            raise Refused(
                f"party {transaction.party_id!r} is not on the related-party "
                "register; a transaction with a stranger is not a related-party "
                "transaction however large it is"
            )
        if transaction.amount.currency != self.currency:
            raise Refused(
                f"this register is in {self.currency}, not "
                f"{transaction.amount.currency}"
            )
        self.transactions.append(transaction)
        return transaction

    def total_with(self, party_id: str) -> Money:
        total = Money.zero(self.currency)
        for item in self.transactions:
            if item.party_id == party_id:
                total = total + item.amount
        return total

    def outstanding_with(self, party_id: str) -> Money:
        total = Money.zero(self.currency)
        for item in self.transactions:
            if item.party_id == party_id and item.outstanding is not None:
                total = total + item.outstanding
        return total

    def total_all(self) -> Money:
        total = Money.zero(self.currency)
        for item in self.transactions:
            total = total + item.amount
        return total

    def by_relationship(self, relationship: Relationship) -> list[RelatedParty]:
        return sorted(
            (p for p in self.parties.values() if p.relationship is relationship),
            key=lambda p: p.id,
        )

    def material_parties(self, threshold: Money) -> list[str]:
        threshold.same_currency(Money.zero(self.currency))
        return sorted(
            party_id
            for party_id in self.parties
            if self.total_with(party_id) >= threshold
        )

    def share_of_revenue(self, party_id: str, revenue: Money) -> Fraction | None:
        if revenue.units == 0:
            return None
        return Fraction(self.total_with(party_id).units, revenue.units)

    def disclosure_lines(self, threshold: Money) -> list[str]:
        lines: list[str] = []
        for party_id in self.material_parties(threshold):
            party = self.parties[party_id]
            total = self.total_with(party_id)
            owed = self.outstanding_with(party_id)
            lines.append(
                f"{party.name} ({party.relationship.value}): "
                f"{total.format()} transacted, {owed.format()} outstanding"
            )
        return lines
