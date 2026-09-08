"""Direct debits: a mandate to pull money, and what happens when the pull fails.

A direct debit reverses the normal direction of payment: the
merchant pulls from the payer's account rather than waiting to be
pushed. That power is fenced by a mandate, the payer's standing
authorization, and the fence has real rules. A first collection
must be pre-notified so the payer knows what is coming and when; a
mandate goes dormant if unused for long enough and must be
reconfirmed rather than silently reused; and a collection after
cancellation is not a late payment, it is an unauthorized
withdrawal. This module enforces those rules rather than treating a
mandate as a flag. Failed collections are the other half: a pull
can be returned days after it appeared to succeed, so a collection
is presented, then either settles or is returned with a reason, and
the module keeps the returned amount out of the settled total.
Counting a presented collection as revenue is how a business books
income it never received and discovers the shortfall a week later
when the returns arrive.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.errors import Refused
from mint.money import Money


class MandateStatus(Enum):
    ACTIVE = "active"
    DORMANT = "dormant"
    CANCELLED = "cancelled"


class CollectionState(Enum):
    PRESENTED = "presented"
    SETTLED = "settled"
    RETURNED = "returned"


@dataclass
class Collection:
    id: str
    amount: Money
    presented_on: datetime.date
    state: CollectionState = CollectionState.PRESENTED
    return_reason: str = ""


@dataclass
class Mandate:
    reference: str
    payer: str
    signed_on: datetime.date
    dormancy_days: int = 395
    cancelled_on: datetime.date | None = None
    last_collected: datetime.date | None = None
    notified: set[str] = field(default_factory=set)
    collections: list[Collection] = field(default_factory=list)

    def status(self, as_of: datetime.date) -> MandateStatus:
        if self.cancelled_on is not None and as_of >= self.cancelled_on:
            return MandateStatus.CANCELLED
        reference_date = self.last_collected or self.signed_on
        if (as_of - reference_date).days > self.dormancy_days:
            return MandateStatus.DORMANT
        return MandateStatus.ACTIVE

    def notify(self, collection_id: str) -> str:
        self.notified.add(collection_id)
        return collection_id

    def is_first_collection(self) -> bool:
        return self.last_collected is None

    def cancel(self, on: datetime.date) -> MandateStatus:
        if self.cancelled_on is not None:
            raise Refused(f"mandate {self.reference!r} is already cancelled")
        self.cancelled_on = on
        return MandateStatus.CANCELLED

    def present(
        self, collection_id: str, amount: Money, on: datetime.date
    ) -> Collection:
        status = self.status(on)
        if status is MandateStatus.CANCELLED:
            raise Refused(
                f"mandate {self.reference!r} was cancelled; a collection against "
                "it is not a late payment, it is an unauthorized withdrawal"
            )
        if status is MandateStatus.DORMANT:
            raise Refused(
                f"mandate {self.reference!r} has gone dormant and must be "
                "reconfirmed before it is used again"
            )
        if not amount.is_positive():
            raise Refused("a collection pulls a positive amount")
        if self.is_first_collection() and collection_id not in self.notified:
            raise Refused(
                f"collection {collection_id!r} is the first on mandate "
                f"{self.reference!r} and must be pre-notified before it is taken"
            )
        collection = Collection(collection_id, amount, on)
        self.collections.append(collection)
        self.last_collected = on
        return collection

    def _find(self, collection_id: str) -> Collection:
        for collection in self.collections:
            if collection.id == collection_id:
                return collection
        raise Refused(f"there is no collection {collection_id!r} on this mandate")

    def settle(self, collection_id: str) -> Collection:
        collection = self._find(collection_id)
        if collection.state is not CollectionState.PRESENTED:
            raise Refused(f"collection {collection_id!r} is already {collection.state.value}")
        collection.state = CollectionState.SETTLED
        return collection

    def mark_returned(self, collection_id: str, reason: str) -> Collection:
        collection = self._find(collection_id)
        if collection.state is CollectionState.RETURNED:
            raise Refused(f"collection {collection_id!r} was already returned")
        if not reason.strip():
            raise Refused("a returned collection carries the reason it failed")
        collection.state = CollectionState.RETURNED
        collection.return_reason = reason.strip()
        return collection

    def settled_total(self, currency: str) -> Money:
        total = Money.zero(currency)
        for collection in self.collections:
            if collection.state is CollectionState.SETTLED:
                total = total + collection.amount
        return total

    def presented_total(self, currency: str) -> Money:
        total = Money.zero(currency)
        for collection in self.collections:
            if collection.state is not CollectionState.RETURNED:
                total = total + collection.amount
        return total

    def returned_total(self, currency: str) -> Money:
        total = Money.zero(currency)
        for collection in self.collections:
            if collection.state is CollectionState.RETURNED:
                total = total + collection.amount
        return total
