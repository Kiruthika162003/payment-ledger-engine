"""Assay: the estimates that can be quietly released to flatter a year are fenced.

A provision is an estimate, and estimates are the softest part of
any set of accounts, which is why the rules around them are the
tightest. Three fences matter here and each is measured. A
discounted provision must unwind to exactly the amount it will pay,
so discounting neither creates money nor loses it over the term. An
impairment reversal must stop at the carrying value the asset would
have had if it had never been impaired, since going past that turns
a write-down into a way of manufacturing a future gain. And a
merely possible obligation must be disclosed rather than provided,
because a provision made too readily becomes a reserve to release
in a bad year. The three are checked together because they are
variations on the same temptation, which is using an estimate to
move profit from one period into another.
"""

from __future__ import annotations

from fractions import Fraction

from mint.assays.framework import Finding, assay
from mint.contingency import (
    Contingency,
    Estimate,
    Likelihood,
    Treatment,
)
from mint.impairment import ImpairableAsset, RecoverableAmount
from mint.money import Money
from mint.provisiondiscount import DiscountedProvision


@assay("provisions", "are the estimates fenced against being released to order")
def _probe() -> list[Finding]:
    findings: list[Finding] = []

    provision = DiscountedProvision(
        id="P-1",
        undiscounted=Money.of("100000.07", "USD"),
        rate=Fraction(5, 100),
        periods=9,
    )
    discount = provision.discount_taken()
    total = provision.unwind_fully()
    findings.append(
        Finding("the unwind lands on the outflow", provision.lands_on_the_outflow(), True)
    )
    findings.append(Finding("the finance cost equals the discount", total, discount))

    asset = ImpairableAsset("A-1", Money.of(100000, "USD"))
    asset.impair(RecoverableAmount(Money.of(60000, "USD"), Money.of(70000, "USD")))
    taken, refused = asset.reverse(
        RecoverableAmount(Money.of(500000, "USD"), Money.of(500000, "USD"))
    )
    findings.append(Finding("the reversal is capped", taken.units, 3000000))
    findings.append(Finding("the excess is refused, not taken", refused.units, 40000000))
    findings.append(
        Finding("carrying value never exceeds the never-impaired one",
                asset.carrying_value.units, 10000000)
    )

    possible = Contingency(
        id="C-1",
        description="a lawsuit that might go either way",
        likelihood=Likelihood.POSSIBLE,
        estimate=Estimate(Money.of(10000, "USD"), Money.of(30000, "USD")),
    )
    findings.append(
        Finding("a possible obligation is disclosed", possible.treatment(), Treatment.DISCLOSE)
    )
    findings.append(
        Finding("and provides nothing", possible.required_provision().units, 0)
    )

    probable = Contingency(
        id="C-2",
        description="a claim we expect to lose",
        likelihood=Likelihood.PROBABLE,
        estimate=Estimate(Money.of(10000, "USD"), Money.of(30000, "USD")),
    )
    findings.append(
        Finding(
            "a probable one provides the midpoint",
            probable.required_provision().units,
            2000000,
        )
    )
    return findings
