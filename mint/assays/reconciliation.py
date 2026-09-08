"""Assay: reconciliation matches true pairs and refuses to hide a real gap.

The failure mode of a reconciler is not missing a match; it is
inventing one, because a false match produces a clean report that
conceals a missing deposit, and a clean report is exactly what
stops anyone from looking further. So this assay measures the two
halves separately. On a set where every ledger line has a genuine
bank partner, possibly cleared a few days later, it confirms the
reconciliation comes back complete with nothing unmatched. On a
set with one deposit truly absent from the bank, it confirms that
line is left unmatched and named rather than paired with something
convenient, since the whole worth of the exercise is that the gap
survives to be seen. The nearest-date preference is measured too,
because a loose match that grabs the farther of two candidates can
strand the pair that should have taken it.
"""

from __future__ import annotations

import datetime

from mint.assays.framework import Finding, assay
from mint.money import Money
from mint.reconcile import Movement, reconcile


def _m(day: int, amount: str, ref: str) -> Movement:
    return Movement(datetime.date(2026, 1, day), Money.of(amount, "USD"), ref)


@assay("reconciliation", "does reconciliation match true pairs and keep real gaps visible")
def _probe() -> list[Finding]:
    findings: list[Finding] = []

    ledger = [_m(1, "100.00", "A"), _m(2, "50.00", "B"), _m(3, "25.00", "C")]
    bank = [_m(1, "100.00", "A"), _m(5, "50.00", "cleared-late"), _m(3, "25.00", "C")]
    clean = reconcile(ledger, bank, window_days=5)
    findings.append(Finding("a genuine set reconciles fully", clean.is_reconciled(), True))
    findings.append(Finding("all three pairs matched", clean.matched_count(), 3))

    missing_bank = [_m(1, "100.00", "A"), _m(3, "25.00", "C")]
    gapped = reconcile(ledger, missing_bank, window_days=5)
    findings.append(
        Finding("the absent deposit stays unmatched", len(gapped.unmatched_ledger), 1)
    )
    findings.append(
        Finding("the unmatched line is the missing one",
                [m.ref for m in gapped.unmatched_ledger], ["B"])
    )

    near = reconcile([_m(4, "70.00", "x")], [_m(2, "70.00", "far"), _m(5, "70.00", "near")], 5)
    findings.append(Finding("the nearest candidate wins", near.matched[0][1].ref, "near"))
    return findings
