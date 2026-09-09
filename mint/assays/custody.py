"""Assay: money held for other people is never quietly turned into your own.

Several modules here hold money that belongs to somebody else: a
petty cash float, a customer's security deposit, an escrow, a
suspense item nobody has identified, a dormant balance awaiting
escheatment. Each of them has the same failure mode, which is
recognizing the money as the holder's own, and each guards against
it differently. This assay checks that the guards hold. The petty
cash equation must balance cash against vouchers and the float. A
treasury sweep must move money between accounts without creating
any. A security deposit must return what was taken plus interest
less only stated deductions. A dormant balance must not be
escheatable before its time. Measuring them together is the point:
each module is convincing on its own, and the question worth asking
is whether the package as a whole ever lets somebody else's money
turn into revenue.
"""

from __future__ import annotations

import datetime

from mint.assays.framework import Finding, assay
from mint.customerdeposit import SecurityDeposit
from mint.errors import Refused
from mint.escheatment import ContactKind, DormantBalance
from mint.money import Money
from mint.pettycash import PettyCash
from mint.suspense import SuspenseAccount
from mint.treasury import SweepAccount, apply_sweep, plan_sweep, total_across

DAY = datetime.date(2026, 2, 1)
LATER = datetime.date(2027, 2, 1)
MUCH_LATER = datetime.date(2030, 1, 1)


@assay("custody", "does money held for others stay held")
def _probe() -> list[Finding]:
    findings: list[Finding] = []

    tin = PettyCash(
        float_amount=Money.of(200, "USD"), cash_on_hand=Money.of(200, "USD")
    )
    tin.spend("v1", Money.of("37.45", "USD"), DAY, "taxi", "alice")
    tin.spend("v2", Money.of("12.55", "USD"), DAY, "stamps", "alice")
    findings.append(Finding("the imprest equation holds", tin.is_balanced(), True))
    findings.append(Finding("the tin variance", tin.variance().units, 0))

    accounts = [
        SweepAccount("hub", Money.of(1000, "USD"), Money.zero("USD"), Money.zero("USD")),
        SweepAccount(
            "ops", Money.of(5000, "USD"), Money.of(2000, "USD"), Money.of(1000, "USD")
        ),
        SweepAccount(
            "pay", Money.of(200, "USD"), Money.of(1500, "USD"), Money.of(1000, "USD")
        ),
    ]
    before = total_across({a.code: a.balance for a in accounts}, "USD")
    plan = plan_sweep(accounts, "hub", "USD")
    after = total_across(apply_sweep(accounts, plan), "USD")
    findings.append(Finding("a sweep creates no money", before == after, True))
    findings.append(Finding("the swept total", after.units, 620000))

    deposit = SecurityDeposit("D-1", "tenant", Money.of(2000, "USD"), DAY)
    deposit.deduct(Money.of(250, "USD"), LATER, "cleaning")
    statement = deposit.statement(LATER)
    findings.append(Finding("a deposit statement reconciles", statement.reconciles(), True))
    findings.append(
        Finding("what the depositor gets back", statement.returned.units, 175000)
    )

    suspense = SuspenseAccount("1999", "USD")
    suspense.park("w1", Money.of(5000, "USD"), DAY, "unidentified wire")
    suspense.get("w1").clear(Money.of(2000, "USD"), LATER, "invoice 501", "alice")
    findings.append(Finding("suspense still holds the rest", suspense.balance().units, 300000))

    dormant = DormantBalance("B-1", "alice", Money.of(250, "USD"), DAY)
    dormant.record_contact(LATER, ContactKind.SYSTEM_GENERATED, "interest posted")
    early_refused = False
    try:
        dormant.escheat(LATER)
    except Refused:
        early_refused = True
    findings.append(Finding("escheating early is refused", early_refused, True))
    findings.append(
        Finding(
            "a system contact did not reset the clock",
            dormant.is_dormant(MUCH_LATER),
            True,
        )
    )
    return findings
