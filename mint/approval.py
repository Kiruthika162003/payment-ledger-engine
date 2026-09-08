"""Maker and checker: nobody posts their own entry, above a threshold at least.

Segregation of duties is the oldest fraud control there is and it
reduces to one rule: the person who prepares an entry is not the
person who approves it. It works because most internal fraud needs
one person to do both, and it fails in exactly one way, which is
allowing the maker to approve their own work when they happen to
have the permission. This module refuses that by identity rather
than by permission level, since a controller who prepares an entry
is still its maker no matter how senior they are. Thresholds are
supported because requiring two people for every ten-dollar entry
means the control gets bypassed by everyone within a week, so small
entries post on one signature and large ones need a second, with
the threshold visible rather than hidden. Entries above a higher
limit need two approvers, both distinct from the maker and from
each other. Nothing posts while an approval is pending, and a
rejected entry records who rejected it and why, because an entry
that simply disappears is one nobody can learn from.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.entry import Entry
from mint.errors import Refused
from mint.ledger import Ledger
from mint.money import Money


class ApprovalState(Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    POSTED = "posted"


@dataclass(frozen=True)
class ApprovalPolicy:
    single_signature_below: Money
    two_approvers_above: Money

    def __post_init__(self) -> None:
        self.two_approvers_above.same_currency(self.single_signature_below)
        if self.two_approvers_above < self.single_signature_below:
            raise Refused(
                "the two-approver limit sits above the single-signature one, "
                "or the thresholds contradict each other"
            )

    def approvals_needed(self, amount: Money) -> int:
        if amount < self.single_signature_below:
            return 0
        if amount > self.two_approvers_above:
            return 2
        return 1


@dataclass
class PendingEntry:
    id: str
    entry: Entry
    maker: str
    policy: ApprovalPolicy
    state: ApprovalState = ApprovalState.DRAFT
    approvals: list[tuple[str, datetime.date]] = field(default_factory=list)
    rejected_by: str | None = None
    rejection_reason: str = ""

    def approvers(self) -> list[str]:
        return [name for name, _ in self.approvals]

    def amount(self) -> Money:
        currency = self.policy.single_signature_below.currency
        return Money.from_minor(self.entry.debit_total(currency), currency)

    def approvals_needed(self) -> int:
        return self.policy.approvals_needed(self.amount())

    def submit(self) -> ApprovalState:
        if self.state is not ApprovalState.DRAFT:
            raise Refused(f"entry {self.id!r} is already {self.state.value}")
        self.state = (
            ApprovalState.APPROVED
            if self.approvals_needed() == 0
            else ApprovalState.PENDING
        )
        return self.state

    def approve(self, approver: str, on: datetime.date) -> ApprovalState:
        if self.state is not ApprovalState.PENDING:
            raise Refused(f"entry {self.id!r} is {self.state.value}, not pending")
        name = approver.strip()
        if not name:
            raise Refused("an approval names the approver")
        if name == self.maker:
            # By identity, not by permission: seniority does not stop someone
            # being the maker of their own entry.
            raise Refused(
                f"{name!r} prepared entry {self.id!r} and cannot approve it; "
                "the maker is never the checker"
            )
        if name in self.approvers():
            raise Refused(f"{name!r} has already approved entry {self.id!r}")
        self.approvals.append((name, on))
        if len(self.approvals) >= self.approvals_needed():
            self.state = ApprovalState.APPROVED
        return self.state

    def reject(self, rejector: str, reason: str) -> ApprovalState:
        if self.state not in (ApprovalState.PENDING, ApprovalState.DRAFT):
            raise Refused(f"entry {self.id!r} is {self.state.value}")
        if not rejector.strip():
            raise Refused("a rejection names who rejected it")
        if not reason.strip():
            raise Refused(
                "a rejection records why; an entry that simply disappears is "
                "one nobody can learn from"
            )
        self.rejected_by = rejector.strip()
        self.rejection_reason = reason.strip()
        self.state = ApprovalState.REJECTED
        return self.state

    def post(self, ledger: Ledger) -> Entry:
        if self.state is not ApprovalState.APPROVED:
            raise Refused(
                f"entry {self.id!r} is {self.state.value} and cannot post; "
                "nothing posts while an approval is outstanding"
            )
        posted = ledger.post(self.entry)
        self.state = ApprovalState.POSTED
        return posted

    def outstanding_approvals(self) -> int:
        return max(0, self.approvals_needed() - len(self.approvals))
