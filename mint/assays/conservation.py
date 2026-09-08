"""Assay: money is conserved through addition and through splitting.

Two of the ledger's foundational promises are that adding money
never drifts and that dividing it never leaks. The first is the
tenth-of-a-dollar test that floating point fails: a tenth added
ten times must be exactly one dollar, not a value a hair off it.
The second is the allocation promise: a sum split any number of
ways, evenly or by weight, must have its parts add back to the
original to the cent. This assay measures both against many
splits rather than one lucky case, because a conservation law that
holds for the example in the docstring and fails on the eleventh
share is not a law.
"""

from __future__ import annotations

from mint.assays.framework import Finding, assay
from mint.money import Money
from mint.rounding import allocate, split


@assay("conservation", "does money survive addition and splitting intact")
def _probe() -> list[Finding]:
    findings: list[Finding] = []

    running = Money.zero("USD")
    for _ in range(10):
        running = running + Money.of("0.10", "USD")
    findings.append(Finding("a tenth summed ten times", running.units, 100))

    total = Money.of("100.00", "USD")
    leaks = 0
    for parts in range(1, 64):
        pieces = split(total, parts)
        if sum(piece.units for piece in pieces) != total.units:
            leaks += 1
    findings.append(Finding("even splits that failed to reconcile", leaks, 0))

    weighted = allocate(Money.of("1.00", "USD"), [1, 1, 1])
    findings.append(
        Finding("a dollar split three ways", [p.units for p in weighted], [34, 33, 33])
    )

    weighted_sum = sum(p.units for p in allocate(Money.of("999.99", "USD"), [7, 11, 13, 17]))
    findings.append(Finding("a weighted split reconciles", weighted_sum, 99999))

    return findings
