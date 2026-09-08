"""Expense reports: claims checked against policy before anyone is reimbursed.

An expense report is a set of claims an employee wants back, and
the control is a policy applied before approval rather than a
conversation afterward. This module checks each claim against the
rules that actually appear in expense policies: a per-category cap,
a requirement that anything above a threshold carries a receipt,
and a ban on dates outside the claim period. Each violation is
reported against the claim that caused it, because an approver
handed a single rejection for a twelve-line report cannot act on
it, while a line-level finding tells them exactly what to send
back. A report with violations can still be approved by someone
with the authority to override, and the override is recorded with
its reason, since policies exist to be applied consistently and
exceptions exist to be visible. The reimbursable total counts only
the claims that pass or were overridden, so the number that reaches
payroll is the number that was actually approved rather than the
number that was submitted.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class Claim:
    id: str
    category: str
    amount: Money
    date: datetime.date
    has_receipt: bool = False
    note: str = ""


@dataclass(frozen=True)
class Violation:
    claim_id: str
    rule: str
    detail: str


@dataclass
class ExpensePolicy:
    currency: str
    caps: dict[str, Money] = field(default_factory=dict)
    receipt_threshold: Money | None = None

    def set_cap(self, category: str, amount: Money) -> Money:
        if amount.currency != self.currency:
            raise Refused(
                f"a cap in {amount.currency} does not belong to a "
                f"{self.currency} policy"
            )
        if not amount.is_positive():
            raise Refused("a category cap is a positive amount")
        self.caps[category] = amount
        return amount

    def check(
        self, claim: Claim, period_start: datetime.date, period_end: datetime.date
    ) -> list[Violation]:
        found: list[Violation] = []
        if claim.amount.currency != self.currency:
            found.append(
                Violation(
                    claim.id,
                    "currency",
                    f"claimed in {claim.amount.currency}, not {self.currency}",
                )
            )
            return found
        cap = self.caps.get(claim.category)
        if cap is not None and claim.amount > cap:
            found.append(
                Violation(
                    claim.id,
                    "category cap",
                    f"{claim.amount.format()} exceeds the {cap.format()} cap for "
                    f"{claim.category}",
                )
            )
        if (
            self.receipt_threshold is not None
            and claim.amount > self.receipt_threshold
            and not claim.has_receipt
        ):
            found.append(
                Violation(
                    claim.id,
                    "receipt required",
                    f"{claim.amount.format()} is above the "
                    f"{self.receipt_threshold.format()} receipt threshold",
                )
            )
        if not period_start <= claim.date <= period_end:
            found.append(
                Violation(
                    claim.id,
                    "outside the period",
                    f"dated {claim.date.isoformat()}, outside the claim period",
                )
            )
        return found


@dataclass
class ExpenseReport:
    id: str
    employee: str
    period_start: datetime.date
    period_end: datetime.date
    policy: ExpensePolicy
    claims: list[Claim] = field(default_factory=list)
    overrides: dict[str, str] = field(default_factory=dict)
    approved_by: str | None = None

    def add(self, claim: Claim) -> Claim:
        if any(existing.id == claim.id for existing in self.claims):
            raise Refused(f"claim {claim.id!r} is already on this report")
        self.claims.append(claim)
        return claim

    def violations(self) -> list[Violation]:
        found: list[Violation] = []
        for claim in self.claims:
            if claim.id in self.overrides:
                continue
            found.extend(
                self.policy.check(claim, self.period_start, self.period_end)
            )
        return found

    def override(self, claim_id: str, approver: str, reason: str) -> str:
        if not any(claim.id == claim_id for claim in self.claims):
            raise Refused(f"there is no claim {claim_id!r} on this report")
        if not reason.strip():
            raise Refused(
                "an override records its reason; exceptions exist to be visible"
            )
        self.overrides[claim_id] = f"{approver.strip()}: {reason.strip()}"
        return self.overrides[claim_id]

    def is_clean(self) -> bool:
        return not self.violations()

    def reimbursable(self) -> Money:
        blocked = {violation.claim_id for violation in self.violations()}
        total = Money.zero(self.policy.currency)
        for claim in self.claims:
            if claim.id in blocked:
                continue
            if claim.amount.currency != self.policy.currency:
                continue
            total = total + claim.amount
        return total

    def submitted_total(self) -> Money:
        total = Money.zero(self.policy.currency)
        for claim in self.claims:
            if claim.amount.currency == self.policy.currency:
                total = total + claim.amount
        return total

    def approve(self, approver: str) -> str:
        if not self.is_clean():
            raise Refused(
                f"report {self.id!r} has {len(self.violations())} unresolved "
                "policy violations; override them or send them back"
            )
        if not approver.strip():
            raise Refused("an approval names the approver")
        self.approved_by = approver.strip()
        return self.approved_by
