"""Assay: every schedule this package builds closes exactly on zero.

Four different modules build schedules that spread an amount over
time, and each has the same failure mode: rounding each period
independently leaves a residue, so the loan still owes a cent after
its last payment, the deferred revenue keeps a liability that can
never be released, and the prepaid asset never fully amortizes.
Each module handles it differently, the loan and the lease by
letting the final period absorb the remainder, the deferral and the
prepayment by allocating with the cent conserved from the start,
and this assay checks all four against the same standard rather
than trusting each in isolation. It runs them on amounts and terms
chosen to divide badly, since a schedule that closes on a round
number and a round term proves nothing, and the interesting case is
always the one whose arithmetic does not come out evenly.
"""

from __future__ import annotations

import datetime
from fractions import Fraction

from mint.amortization import schedule as loan_schedule
from mint.assays.framework import Finding, assay
from mint.deferral import monthly_schedule
from mint.lease import schedule as lease_schedule
from mint.money import Money
from mint.prepaid import monthly_amortization

START = datetime.date(2026, 1, 1)

# Amounts and terms chosen to divide badly on purpose.
AWKWARD = [
    (Money.of("1000.00", "USD"), 7),
    (Money.of("999.99", "USD"), 13),
    (Money.of("100.00", "USD"), 3),
    (Money.of("12345.67", "USD"), 11),
]


@assay("schedules", "does every schedule close exactly on zero")
def _probe() -> list[Finding]:
    findings: list[Finding] = []

    loan_residues = 0
    for amount, periods in AWKWARD:
        result = loan_schedule(amount, Fraction(7, 100), periods, 12)
        if result.final_balance() != 0:
            loan_residues += 1
    findings.append(Finding("loan schedules left owing", loan_residues, 0))

    lease_residues = 0
    for amount, periods in AWKWARD:
        result = lease_schedule(amount, Fraction(1, 100), periods)
        if not result.closes():
            lease_residues += 1
    findings.append(Finding("lease schedules not closed", lease_residues, 0))

    deferral_residues = 0
    for amount, periods in AWKWARD:
        result = monthly_schedule(amount, START, periods)
        if not result.fully_recognized():
            deferral_residues += 1
    findings.append(Finding("deferrals left deferred", deferral_residues, 0))

    prepaid_residues = 0
    for amount, periods in AWKWARD:
        result = monthly_amortization(amount, START, periods)
        if not result.fully_amortized():
            prepaid_residues += 1
    findings.append(Finding("prepayments left unamortized", prepaid_residues, 0))

    sample = monthly_schedule(Money.of("100.00", "USD"), START, 3)
    findings.append(
        Finding(
            "a hundred over three months",
            [row.recognized for row in sample.rows],
            [3334, 3333, 3333],
        )
    )
    return findings
