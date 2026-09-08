"""Remittance advice: applying a payment the way the payer said to, and flagging short pays.

A customer paying several invoices sends a remittance advice saying
which invoices the payment covers and for how much. Applying it is
mostly clerical until the numbers disagree, and they disagree
often: the advice pays an invoice short because the customer
deducted something, or it references an invoice that does not
exist, or the total on the advice does not match the money that
actually arrived. Each of those means something different and needs
a different person to look at it, so this module classifies rather
than lumping them together. A short pay is applied at the amount
stated and the difference is reported as a deduction to be chased.
An unknown reference is not applied at all, because guessing which
invoice was meant is how a customer's account becomes a mystery. A
total mismatch between the advice and the cash received is reported
before anything is applied, since applying an advice that does not
match the money leaves the ledger out of step with the bank.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class AdviceLine:
    invoice_id: str
    amount: Money


@dataclass(frozen=True)
class OpenInvoice:
    id: str
    balance: Money


@dataclass(frozen=True)
class Application:
    invoice_id: str
    applied: Money
    deduction: Money

    def is_short_pay(self) -> bool:
        return self.deduction.is_positive()


@dataclass(frozen=True)
class AdviceResult:
    applications: tuple[Application, ...]
    unknown_references: tuple[str, ...]
    overpaid: tuple[str, ...]
    unapplied: Money

    def total_applied(self) -> Money:
        total = self.unapplied - self.unapplied
        for application in self.applications:
            total = total + application.applied
        return total

    def short_pays(self) -> tuple[Application, ...]:
        return tuple(item for item in self.applications if item.is_short_pay())

    def is_clean(self) -> bool:
        return (
            not self.unknown_references
            and not self.overpaid
            and not self.short_pays()
            and self.unapplied.is_zero()
        )


@dataclass
class RemittanceAdvice:
    payer: str
    currency: str
    cash_received: Money
    lines: list[AdviceLine] = field(default_factory=list)

    def add(self, invoice_id: str, amount: Money) -> AdviceLine:
        if amount.currency != self.currency:
            raise Refused(
                f"line {invoice_id!r} is in {amount.currency}, not the advice "
                f"currency {self.currency}"
            )
        if not amount.is_positive():
            raise Refused("a remittance line pays a positive amount")
        line = AdviceLine(invoice_id, amount)
        self.lines.append(line)
        return line

    def advice_total(self) -> Money:
        total = Money.zero(self.currency)
        for line in self.lines:
            total = total + line.amount
        return total

    def matches_cash(self) -> bool:
        return self.advice_total() == self.cash_received

    def apply(self, invoices: list[OpenInvoice]) -> AdviceResult:
        if not self.matches_cash():
            raise Refused(
                f"the advice totals {self.advice_total().format()} but "
                f"{self.cash_received.format()} arrived; applying it would leave "
                "the ledger out of step with the bank"
            )
        by_id = {invoice.id: invoice for invoice in invoices}
        applications: list[Application] = []
        unknown: list[str] = []
        overpaid: list[str] = []
        unapplied = Money.zero(self.currency)

        for line in self.lines:
            invoice = by_id.get(line.invoice_id)
            if invoice is None:
                # Never guessed at: a mystery invoice becomes a mystery account.
                unknown.append(line.invoice_id)
                unapplied = unapplied + line.amount
                continue
            if line.amount > invoice.balance:
                overpaid.append(line.invoice_id)
                applications.append(
                    Application(
                        line.invoice_id, invoice.balance, Money.zero(self.currency)
                    )
                )
                unapplied = unapplied + (line.amount - invoice.balance)
                continue
            deduction = invoice.balance - line.amount
            applications.append(Application(line.invoice_id, line.amount, deduction))

        return AdviceResult(
            applications=tuple(applications),
            unknown_references=tuple(unknown),
            overpaid=tuple(overpaid),
            unapplied=unapplied,
        )
