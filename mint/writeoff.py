"""Write-offs: admitting a receivable will not be collected, with a reason and a limit.

A write-off is the moment a business stops pretending a debt will
be paid, and it is a decision rather than a calculation, so the
controls around it matter more than the arithmetic. This module
requires a reason and an authorizer on every write-off, because an
uncontrolled write-off is the simplest embezzlement there is: take
the customer's cash and write off their balance. It enforces an
approval threshold, so amounts above a stated limit need an
authorizer with a higher level rather than whoever happened to be
at the terminal. A write-off cannot exceed the outstanding balance,
and writing off an already-settled balance is refused rather than
silently doing nothing. Recovery is modelled too, since written-off
debts sometimes pay: a recovery is recorded against the write-off
it reverses rather than as fresh revenue, which keeps the history
readable and stops a business from booking the same dollar as
income twice, once when invoiced and again when recovered.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class WriteOff:
    id: str
    date: datetime.date
    amount: Money
    reason: str
    authorized_by: str


@dataclass
class WriteOffPolicy:
    threshold: Money
    senior_approvers: frozenset[str]

    def check(self, amount: Money, approver: str) -> None:
        amount.same_currency(self.threshold)
        if amount > self.threshold and approver not in self.senior_approvers:
            raise Refused(
                f"a write-off of {amount.format()} exceeds the "
                f"{self.threshold.format()} limit and needs a senior approver; "
                f"{approver!r} is not one"
            )


@dataclass
class ReceivableAccount:
    party_id: str
    outstanding: Money
    write_offs: list[WriteOff] = field(default_factory=list)
    recovered: list[tuple[str, Money, datetime.date]] = field(default_factory=list)

    def written_off_total(self) -> Money:
        total = Money.zero(self.outstanding.currency)
        for item in self.write_offs:
            total = total + item.amount
        return total

    def recovered_total(self) -> Money:
        total = Money.zero(self.outstanding.currency)
        for _, amount, _date in self.recovered:
            total = total + amount
        return total

    def write_off(
        self,
        write_off_id: str,
        amount: Money,
        on: datetime.date,
        reason: str,
        authorized_by: str,
        policy: WriteOffPolicy | None = None,
    ) -> WriteOff:
        amount.same_currency(self.outstanding)
        if not reason.strip():
            raise Refused(
                "a write-off needs a reason; an uncontrolled write-off is the "
                "simplest embezzlement there is"
            )
        if not authorized_by.strip():
            raise Refused("a write-off names the person who authorized it")
        if not amount.is_positive():
            raise Refused("a write-off is for a positive amount")
        if self.outstanding.is_zero():
            raise Refused(
                f"the balance for {self.party_id!r} is already settled; there "
                "is nothing to write off"
            )
        if amount > self.outstanding:
            raise Refused(
                f"a write-off of {amount.format()} exceeds the "
                f"{self.outstanding.format()} outstanding for {self.party_id!r}"
            )
        if policy is not None:
            policy.check(amount, authorized_by.strip())
        item = WriteOff(write_off_id, on, amount, reason.strip(), authorized_by.strip())
        self.write_offs.append(item)
        self.outstanding = self.outstanding - amount
        return item

    def recover(self, write_off_id: str, amount: Money, on: datetime.date) -> Money:
        match = next((w for w in self.write_offs if w.id == write_off_id), None)
        if match is None:
            raise Refused(f"there is no write-off {write_off_id!r} to recover against")
        amount.same_currency(self.outstanding)
        already = sum(
            value.units for ident, value, _ in self.recovered if ident == write_off_id
        )
        if amount.units + already > match.amount.units:
            raise Refused(
                f"a recovery of {amount.format()} would exceed the "
                f"{match.amount.format()} written off under {write_off_id!r}"
            )
        self.recovered.append((write_off_id, amount, on))
        return self.recovered_total()
