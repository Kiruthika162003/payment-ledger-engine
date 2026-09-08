"""Assay: the three controls that catch a corrupted import actually catch one.

This repository has three defences against a damaged or tampered
batch of instructions, and each is only worth its complexity if it
fires when it should. The batch poster claims to be all or nothing,
so this assay hands it a batch with one bad entry among good ones
and confirms the ledger is untouched afterward, which is the whole
promise: an operator can fix the file and run it again without
hunting for what already posted. The payment file claims its
control totals catch a lost line and an altered amount, so the
assay damages a rendered file in each way and confirms each is
detected and named. Gapless numbering claims no number is ever
skipped even when one is reserved and abandoned, so the assay
reserves, releases, and issues, and confirms the sequence has no
hole. Each of these is trivially easy to implement in a way that
looks right and never actually fires, which is why they are
measured together rather than trusted.
"""

from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.assays.framework import Finding, assay
from mint.batch import Batch
from mint.chart import Chart
from mint.entry import entry
from mint.ledger import Ledger
from mint.money import Money
from mint.paymentfile import PaymentFile, verify
from mint.posting import credit, debit
from mint.sequence import GaplessSequence

DAY = datetime.date(2026, 8, 1)
AT = datetime.datetime(2026, 8, 1, 9, 0)


def _ledger() -> Ledger:
    chart = Chart()
    chart.add("1000", "Cash", AccountType.ASSET, "USD")
    chart.add("4000", "Sales", AccountType.INCOME, "USD")
    return Ledger(chart)


def _good():
    return entry(
        [debit("1000", Money.of(100, "USD")), credit("4000", Money.of(100, "USD"))], DAY
    )


def _bad():
    return entry(
        [debit("9999", Money.of(100, "USD")), credit("4000", Money.of(100, "USD"))], DAY
    )


def _file() -> PaymentFile:
    payment_file = PaymentFile("F-1", "USD", DAY, "1000")
    payment_file.add("P-1", "Acme", "GB82", Money.of(500, "USD"))
    payment_file.add("P-2", "Beta", "GB82", Money.of(250, "USD"))
    payment_file.add("P-3", "Gamma", "GB82", Money.of(125, "USD"))
    return payment_file


@assay("controls", "do the batch, file, and numbering controls fire when they should")
def _probe() -> list[Finding]:
    findings: list[Finding] = []

    ledger = _ledger()
    batch = Batch("B-1")
    batch.add(_good())
    batch.add(_bad())
    batch.add(_good())
    result = batch.commit(ledger, AT)
    findings.append(Finding("a bad batch posts nothing", result.posted, 0))
    findings.append(Finding("the ledger is untouched", ledger.entry_count(), 0))
    findings.append(
        Finding("the bad entry is named by position", result.first_problem().position, 1)
    )

    clean = _ledger()
    good_batch = Batch("B-2")
    good_batch.add(_good())
    good_batch.add(_good())
    findings.append(
        Finding("a clean batch posts in full", good_batch.commit(clean, AT).posted, 2)
    )

    lines = _file().render()
    intact = verify("\n".join(lines))
    findings.append(Finding("an intact file verifies", intact.is_intact(), True))

    short = list(lines)
    del short[2]
    short_result = verify("\n".join(short))
    findings.append(
        Finding("a lost line fails the count", short_result.count_matches(), False)
    )

    altered = list(lines)
    altered[1] = altered[1].replace("|50000", "|95000")
    tampered = verify("\n".join(altered))
    findings.append(
        Finding("an altered amount fails the sum", tampered.total_matches(), False)
    )
    findings.append(
        Finding("the count still passes on a tamper", tampered.count_matches(), True)
    )

    sequence = GaplessSequence(prefix="INV-")
    sequence.issue()
    sequence.reserve()
    sequence.release()
    sequence.issue()
    sequence.issue()
    findings.append(Finding("an abandoned number leaves no hole", sequence.has_gaps(), False))
    findings.append(Finding("the sequence issued three", sequence.issued, [1, 2, 3]))
    return findings
