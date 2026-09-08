"""Suspense: the parking space for money that arrived without a name on it.

Money arrives that nobody can identify: a wire with no reference, a
payment from a customer whose name does not match any account. It
cannot be ignored, because it is real money sitting in a real bank
account, and it cannot be guessed at, because crediting the wrong
customer creates two problems where there was one. Suspense is the
answer: the receipt is recorded against a holding account so the
cash is on the books, and it stays there until someone identifies
it. The discipline that makes suspense work rather than becoming a
dumping ground is aging: an item in suspense is a question nobody
has answered, so this module tracks how long each has sat and
reports the stale ones, since the value of the account is entirely
in it being emptied. Clearing an item requires naming what it
turned out to be, and partial clearing is supported because one
wire often covers several invoices with a remainder that stays
unidentified. The balance is always the sum of the unclesared
items, so the account can be reconciled against the ledger exactly.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class Clearing:
    date: datetime.date
    amount: Money
    identified_as: str
    by: str


@dataclass
class SuspenseItem:
    id: str
    amount: Money
    received: datetime.date
    description: str
    clearings: list[Clearing] = field(default_factory=list)

    def cleared_total(self) -> Money:
        total = Money.zero(self.amount.currency)
        for clearing in self.clearings:
            total = total + clearing.amount
        return total

    def outstanding(self) -> Money:
        return self.amount - self.cleared_total()

    def is_cleared(self) -> bool:
        return self.outstanding().is_zero()

    def age_days(self, as_of: datetime.date) -> int:
        return max(0, (as_of - self.received).days)

    def clear(
        self, amount: Money, on: datetime.date, identified_as: str, by: str
    ) -> Clearing:
        amount.same_currency(self.amount)
        if not amount.is_positive():
            raise Refused("a clearing moves a positive amount out of suspense")
        if not identified_as.strip():
            raise Refused(
                "a clearing names what the money turned out to be; guessing "
                "creates two problems where there was one"
            )
        if not by.strip():
            raise Refused("a clearing names who identified the item")
        if amount > self.outstanding():
            raise Refused(
                f"a clearing of {amount.format()} exceeds the "
                f"{self.outstanding().format()} still unidentified in item "
                f"{self.id!r}"
            )
        clearing = Clearing(on, amount, identified_as.strip(), by.strip())
        self.clearings.append(clearing)
        return clearing


@dataclass
class SuspenseAccount:
    code: str
    currency: str
    stale_after_days: int = 30
    items: list[SuspenseItem] = field(default_factory=list)

    def park(
        self, item_id: str, amount: Money, on: datetime.date, description: str
    ) -> SuspenseItem:
        if amount.currency != self.currency:
            raise Refused(
                f"suspense account {self.code!r} holds {self.currency}, not "
                f"{amount.currency}"
            )
        if not amount.is_positive():
            raise Refused("a suspense item holds a positive amount")
        if any(existing.id == item_id for existing in self.items):
            raise Refused(f"item {item_id!r} is already in suspense")
        item = SuspenseItem(item_id, amount, on, description)
        self.items.append(item)
        return item

    def get(self, item_id: str) -> SuspenseItem:
        for item in self.items:
            if item.id == item_id:
                return item
        raise Refused(f"there is no suspense item {item_id!r}")

    def balance(self) -> Money:
        total = Money.zero(self.currency)
        for item in self.items:
            total = total + item.outstanding()
        return total

    def open_items(self) -> list[SuspenseItem]:
        return [item for item in self.items if not item.is_cleared()]

    def stale_items(self, as_of: datetime.date) -> list[SuspenseItem]:
        return [
            item
            for item in self.open_items()
            if item.age_days(as_of) > self.stale_after_days
        ]

    def oldest_open(self, as_of: datetime.date) -> SuspenseItem | None:
        open_items = self.open_items()
        if not open_items:
            return None
        return max(open_items, key=lambda item: item.age_days(as_of))

    def is_empty(self) -> bool:
        return self.balance().is_zero()
