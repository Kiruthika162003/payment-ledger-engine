"""Assay: netting moves less money and leaves every party exactly where it was.

Netting is worth doing only if it is safe, and safe means one
thing: no party's net position changes. It is easy to write a
netting routine that produces a smaller set of payments and quietly
leaves someone a few dollars out, because the saving looks like
success and nobody checks the positions afterward. So this assay
checks the positions rather than the saving. It measures a perfect
circle of debt, where every party owes exactly what it is owed and
the honest answer is that no money needs to move at all, and an
uneven web where real payments remain, confirming in both cases
that the instructions reproduce the net positions the obligations
implied. It also measures that the instructions are deterministic,
since a netting run that produces different payments on identical
input cannot be checked by running it again, which is how these
things are checked in practice.
"""

from __future__ import annotations

from mint.assays.framework import Finding, assay
from mint.money import Money
from mint.netting import NettingCycle


def _circle() -> NettingCycle:
    cycle = NettingCycle("USD")
    cycle.add("A", "B", Money.of(100, "USD"))
    cycle.add("B", "C", Money.of(100, "USD"))
    cycle.add("C", "A", Money.of(100, "USD"))
    return cycle


def _web() -> NettingCycle:
    cycle = NettingCycle("USD")
    cycle.add("A", "B", Money.of(500, "USD"))
    cycle.add("B", "C", Money.of(300, "USD"))
    cycle.add("C", "A", Money.of(100, "USD"))
    cycle.add("D", "A", Money.of(250, "USD"))
    cycle.add("B", "D", Money.of(75, "USD"))
    return cycle


@assay("netting", "does netting move less while leaving every position unchanged")
def _probe() -> list[Finding]:
    findings: list[Finding] = []

    circle = _circle()
    findings.append(Finding("a perfect circle moves nothing", circle.netted_total().units, 0))
    findings.append(Finding("the circle's gross avoided", circle.saving().units, 30000))

    web = _web()
    findings.append(
        Finding("positions preserved on a real web", web.positions_preserved(), True)
    )
    findings.append(
        Finding(
            "netted moves less than gross",
            web.netted_total() < web.gross_total(),
            True,
        )
    )
    # A owes a net 150 and D a net 175, so only 325 moves against a gross
    # of 1225; the first guess here was more than twice the measured figure.
    findings.append(Finding("netted total measured", web.netted_total().units, 32500))
    findings.append(Finding("gross total measured", web.gross_total().units, 122500))

    first = [(i.payer, i.payee, i.amount.units) for i in _web().instructions()]
    second = [(i.payer, i.payee, i.amount.units) for i in _web().instructions()]
    findings.append(Finding("instructions are deterministic", first == second, True))
    return findings
