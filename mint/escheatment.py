"""Escheatment: balances nobody has claimed, and the day they stop being yours to keep.

Money a business holds for someone who has vanished, an uncashed
refund, a dormant wallet, a credit balance on a closed account, does
not become the business's money simply because nobody asked for it.
After a dormancy period set by law it must be handed to the state,
which is escheatment, and the two failures around it are equally
expensive: booking dormant balances to income is taking money that
is not yours, and holding them forever accrues a liability plus
penalties. This module tracks the dormancy clock, which is the part
that gets implemented wrongly: the clock runs from the last
owner-initiated contact, not from the last time anything touched
the account, so a system-generated interest posting or a
maintenance fee does not reset it. Distinguishing owner activity
from system activity is therefore the whole job, and this module
requires each contact to say which it was rather than inferring it.
Balances are reported by the year they will become reportable, since
that is how the filing is organized.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.errors import Refused
from mint.money import Money


class ContactKind(Enum):
    OWNER_INITIATED = "owner_initiated"
    SYSTEM_GENERATED = "system_generated"


@dataclass(frozen=True)
class Contact:
    date: datetime.date
    kind: ContactKind
    description: str

    def resets_the_clock(self) -> bool:
        # Only the owner's own activity counts; an interest posting or a fee
        # the system applied is not the owner being heard from.
        return self.kind is ContactKind.OWNER_INITIATED


@dataclass
class DormantBalance:
    id: str
    owner: str
    amount: Money
    opened: datetime.date
    dormancy_years: int = 3
    contacts: list[Contact] = field(default_factory=list)
    escheated_on: datetime.date | None = None

    def __post_init__(self) -> None:
        if not self.amount.is_positive():
            raise Refused("a dormant balance holds a positive amount")
        if self.dormancy_years < 1:
            raise Refused("a dormancy period runs at least a year")

    def record_contact(
        self, on: datetime.date, kind: ContactKind, description: str
    ) -> Contact:
        if not description.strip():
            raise Refused("a contact record says what happened")
        contact = Contact(on, kind, description.strip())
        self.contacts.append(contact)
        return contact

    def last_owner_contact(self) -> datetime.date:
        owner_contacts = [c.date for c in self.contacts if c.resets_the_clock()]
        return max(owner_contacts) if owner_contacts else self.opened

    def dormant_since(self) -> datetime.date:
        return self.last_owner_contact()

    def reportable_from(self) -> datetime.date:
        anchor = self.dormant_since()
        return datetime.date(
            anchor.year + self.dormancy_years, anchor.month, min(anchor.day, 28)
        )

    def is_dormant(self, as_of: datetime.date) -> bool:
        return as_of >= self.reportable_from()

    def is_escheated(self) -> bool:
        return self.escheated_on is not None

    def days_until_reportable(self, as_of: datetime.date) -> int:
        return max(0, (self.reportable_from() - as_of).days)

    def escheat(self, on: datetime.date) -> Money:
        if self.is_escheated():
            raise Refused(f"balance {self.id!r} was already escheated")
        if not self.is_dormant(on):
            raise Refused(
                f"balance {self.id!r} is not reportable until "
                f"{self.reportable_from().isoformat()}; handing it over early "
                "gives away money the owner may still claim"
            )
        self.escheated_on = on
        return self.amount


@dataclass
class EscheatmentRegister:
    currency: str
    balances: list[DormantBalance] = field(default_factory=list)

    def add(self, balance: DormantBalance) -> DormantBalance:
        if balance.amount.currency != self.currency:
            raise Refused(
                f"balance {balance.id!r} is in {balance.amount.currency}, not "
                f"{self.currency}"
            )
        if any(existing.id == balance.id for existing in self.balances):
            raise Refused(f"balance {balance.id!r} is already registered")
        self.balances.append(balance)
        return balance

    def reportable(self, as_of: datetime.date) -> list[DormantBalance]:
        return [
            balance
            for balance in self.balances
            if balance.is_dormant(as_of) and not balance.is_escheated()
        ]

    def total_reportable(self, as_of: datetime.date) -> Money:
        total = Money.zero(self.currency)
        for balance in self.reportable(as_of):
            total = total + balance.amount
        return total

    def held_total(self) -> Money:
        total = Money.zero(self.currency)
        for balance in self.balances:
            if not balance.is_escheated():
                total = total + balance.amount
        return total

    def by_reporting_year(self) -> dict[int, Money]:
        buckets: dict[int, int] = {}
        for balance in self.balances:
            if balance.is_escheated():
                continue
            year = balance.reportable_from().year
            buckets[year] = buckets.get(year, 0) + balance.amount.units
        return {
            year: Money.from_minor(units, self.currency)
            for year, units in sorted(buckets.items())
        }
