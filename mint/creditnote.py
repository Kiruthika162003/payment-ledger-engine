"""Credit notes: reducing an invoice after it was issued, without editing it.

Once an invoice has been sent it is a document of record, and the
way to reduce what a customer owes is not to edit it but to issue a
credit note against it. The distinction is not bureaucratic: the
original invoice may already be in the customer's system, in a tax
return, or in a period that has been closed, and changing its total
would leave two versions of one document in the world. This module
issues credit notes against an invoice, tracks the total credited,
and refuses to credit more than the invoice was for, since a credit
beyond the invoice is a payment to the customer dressed as a
correction and belongs in its own transaction. Credits carry a
reason, because a credit note is the line an auditor stops on and
an unexplained one invites the question every finance team dreads.
The module reports the net amount now owed, which is the invoice
less its credits, and whether the invoice has been fully credited,
a state worth naming since a fully credited invoice is economically
cancelled while still existing as the record it must remain.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class CreditNote:
    id: str
    date: datetime.date
    amount: Money
    reason: str


@dataclass
class CreditedInvoice:
    invoice_id: str
    invoice_amount: Money
    issued: datetime.date
    credits: list[CreditNote] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.invoice_amount.is_positive():
            raise Refused("an invoice to credit is for a positive amount")

    def credited_total(self) -> Money:
        total = Money.zero(self.invoice_amount.currency)
        for note in self.credits:
            total = total + note.amount
        return total

    def creditable(self) -> Money:
        return self.invoice_amount - self.credited_total()

    def net_owed(self) -> Money:
        return self.creditable()

    def is_fully_credited(self) -> bool:
        return self.creditable().is_zero()

    def issue(
        self, note_id: str, amount: Money, on: datetime.date, reason: str
    ) -> CreditNote:
        amount.same_currency(self.invoice_amount)
        if not amount.is_positive():
            raise Refused("a credit note is for a positive amount")
        if not reason.strip():
            raise Refused(
                "a credit note needs a reason; an unexplained credit is the "
                "line an auditor stops on"
            )
        if on < self.issued:
            raise Refused(
                f"credit note {note_id!r} predates invoice {self.invoice_id!r}"
            )
        if amount > self.creditable():
            raise Refused(
                f"a credit of {amount.format()} exceeds the "
                f"{self.creditable().format()} still creditable on invoice "
                f"{self.invoice_id!r}; a credit beyond the invoice is a payment"
            )
        note = CreditNote(note_id, on, amount, reason.strip())
        self.credits.append(note)
        return note

    def cancel(self, note_id: str, on: datetime.date, reason: str) -> CreditNote:
        return self.issue(note_id, self.creditable(), on, reason)
