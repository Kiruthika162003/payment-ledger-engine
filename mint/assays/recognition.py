"""Assay: everything deferred is eventually recognized, and never more than once.

Four modules here hold something back and release it over time: a
revenue contract releases as obligations are satisfied, a grant
releases as the costs it subsidizes are incurred, deferred revenue
releases across the service period, and a prepayment releases as
the coverage is used. Each has the same pair of failure modes, and
they are opposite. Releasing too little strands a balance that can
never be cleared, so the liability sits on the sheet forever and
somebody eventually writes it off as a gain nobody earned.
Releasing too much recognizes revenue twice. This assay drives each
of the four to completion on an amount that does not divide evenly
and confirms the balance reaches exactly zero and the total
released equals exactly what was held, which is the only pair of
statements that rules both failures out together.
"""

from __future__ import annotations

import datetime
from fractions import Fraction

from mint.assays.framework import Finding, assay
from mint.deferral import monthly_schedule
from mint.grant import Grant, GrantKind
from mint.money import Money
from mint.prepaid import monthly_amortization
from mint.revenuecontract import Obligation, RevenueContract

START = datetime.date(2026, 1, 1)
AWKWARD = Money.of("10000.07", "USD")


@assay("recognition", "is everything deferred released exactly once and in full")
def _probe() -> list[Finding]:
    findings: list[Finding] = []

    contract = RevenueContract("R-1", AWKWARD, START)
    contract.add(Obligation("device", Money.of(600, "USD")))
    contract.add(Obligation("service", Money.of(500, "USD"), over_time=True))
    contract.add(Obligation("install", Money.of(100, "USD")))
    contract.allocate_price()
    for obligation in contract.obligations:
        contract.satisfy(obligation.name, Fraction(1))
    findings.append(
        Finding("a contract recognizes its whole price", contract.recognized_revenue(), AWKWARD)
    )
    findings.append(
        Finding("nothing is left as a liability", contract.contract_liability().units, 0)
    )

    grant = Grant(
        id="G-1",
        amount=AWKWARD,
        kind=GrantKind.ASSET_RELATED,
        received=START,
        periods=7,
    )
    for _ in range(7):
        grant.release_next()
    findings.append(Finding("a grant releases in full", grant.released, AWKWARD))
    findings.append(Finding("no grant balance is stranded", grant.deferred_balance().units, 0))

    deferral = monthly_schedule(AWKWARD, START, 11)
    findings.append(
        Finding("deferred revenue is fully recognized", deferral.fully_recognized(), True)
    )
    findings.append(
        Finding(
            "the deferral releases exactly what was held",
            deferral.rows[-1].cumulative,
            AWKWARD.units,
        )
    )

    prepaid = monthly_amortization(AWKWARD, START, 13)
    findings.append(
        Finding("a prepayment fully amortizes", prepaid.fully_amortized(), True)
    )
    findings.append(
        Finding(
            "the prepayment expenses exactly what was paid",
            prepaid.rows[-1].cumulative,
            AWKWARD.units,
        )
    )
    return findings
