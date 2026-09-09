"""Assay: the controls that need a second person actually need a second person.

Several controls in this package exist to stop one person acting
alone, and each of them is easy to implement in a way that looks
right and lets the one case through that matters. Maker-checker
must refuse the preparer as their own approver by identity, not by
permission level, because a controller who prepared an entry is
still its maker. A write-off above the threshold must need a senior
approver rather than whoever is at the terminal. A review queue
must not let two people claim the same case, since two independent
approvals of one payment is the outcome the queue exists to
prevent. And an expense override must record who granted it and
why. This assay drives each control to the exact case it is meant
to catch and confirms the refusal, because a control that passes
every ordinary case and fails the adversarial one has provided
nothing but paperwork.
"""

from __future__ import annotations

import datetime

from mint.approval import ApprovalPolicy, PendingEntry
from mint.assays.framework import Finding, assay
from mint.entry import entry
from mint.errors import Refused
from mint.expensereport import Claim, ExpensePolicy, ExpenseReport
from mint.money import Money
from mint.posting import credit, debit
from mint.reviewqueue import ReviewItem, ReviewQueue
from mint.writeoff import ReceivableAccount, WriteOffPolicy

DAY = datetime.date(2026, 4, 1)
NOW = datetime.datetime(2026, 4, 1, 12, 0)


def _refuses(action) -> bool:
    try:
        action()
    except Refused:
        return True
    return False


@assay("duty", "do the two-person controls refuse the one case that matters")
def _probe() -> list[Finding]:
    findings: list[Finding] = []

    built = entry(
        [debit("1000", Money.of(500, "USD")), credit("4000", Money.of(500, "USD"))],
        DAY,
    )
    policy = ApprovalPolicy(
        single_signature_below=Money.of(100, "USD"),
        two_approvers_above=Money.of(10000, "USD"),
    )
    pending = PendingEntry("E-1", built, "alice", policy)
    pending.submit()
    findings.append(
        Finding("the maker cannot approve their own entry",
                _refuses(lambda: pending.approve("alice", DAY)), True)
    )
    approved = pending.approve("bob", DAY)
    findings.append(Finding("another person can", approved.value, "approved"))

    account = ReceivableAccount("c1", Money.of(1000, "USD"))
    write_off_policy = WriteOffPolicy(Money.of(500, "USD"), frozenset({"controller"}))
    findings.append(
        Finding(
            "a large write-off needs a senior approver",
            _refuses(
                lambda: account.write_off(
                    "w1", Money.of(600, "USD"), DAY, "gone", "clerk", write_off_policy
                )
            ),
            True,
        )
    )
    findings.append(
        Finding(
            "an unexplained write-off is refused",
            _refuses(
                lambda: account.write_off("w2", Money.of(10, "USD"), DAY, "  ", "clerk")
            ),
            True,
        )
    )

    queue = ReviewQueue()
    queue.add(
        ReviewItem(
            id="R-1",
            subject="txn-1",
            priority=5,
            created=NOW,
            due=NOW + datetime.timedelta(hours=1),
        )
    )
    queue.claim("R-1", "alice", NOW)
    findings.append(
        Finding("two reviewers cannot claim one case",
                _refuses(lambda: queue.claim("R-1", "bob", NOW)), True)
    )
    findings.append(
        Finding("an anonymous resolution is refused",
                _refuses(lambda: queue.resolve("R-1", "  ", True, "fine")), True)
    )

    expense_policy = ExpensePolicy(currency="USD", receipt_threshold=Money.of(25, "USD"))
    expense_policy.set_cap("meals", Money.of(60, "USD"))
    report = ExpenseReport("ER-1", "alice", DAY, DAY, expense_policy)
    report.add(Claim("c1", "meals", Money.of(90, "USD"), DAY, has_receipt=True))
    findings.append(
        Finding("an over-cap claim blocks approval",
                _refuses(lambda: report.approve("manager")), True)
    )
    findings.append(
        Finding("an override without a reason is refused",
                _refuses(lambda: report.override("c1", "manager", " ")), True)
    )
    report.override("c1", "manager", "client dinner agreed in advance")
    findings.append(
        Finding("a recorded override clears it", report.approve("manager"), "manager")
    )
    return findings
