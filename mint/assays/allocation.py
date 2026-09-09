"""Assay: everything in this package that divides a sum puts it all back.

Eight different modules take one amount and divide it into parts,
and every one of them is a place a cent can go missing. The
marketplace split, the overhead allocation, the milestone contract,
the revenue contract, the dividend, the payment plan, the budget
phasing, and the chart mapping all lean on the same
cent-conserving allocation underneath, but each wraps it
differently and a wrapper is exactly where a rounding gets
reintroduced. So this assay divides an awkward amount through every
one of them and measures the sum of the parts against the original.
The amounts are chosen not to divide evenly, because a division
that works on a round number and a round count proves nothing at
all, and the interesting case is always the one whose arithmetic
does not come out.
"""

from __future__ import annotations

import datetime
from fractions import Fraction

from mint.accountmapping import ChartMapping
from mint.assays.framework import Finding, assay
from mint.budgetphasing import Profile, phase
from mint.collections import PaymentPlan
from mint.costallocation import AllocationRun, CostCentre, CostPool
from mint.dividend import ShareRegister, declare
from mint.marketplace import SellerLine, split_payment
from mint.milestone import MilestoneContract
from mint.money import Money
from mint.revenuecontract import Obligation, RevenueContract

DAY = datetime.date(2026, 5, 1)
AWKWARD = Money.of("100000.07", "USD")


def _sum(amounts) -> int:
    return sum(amount.units for amount in amounts)


@assay("allocation", "does every division in this package put the whole sum back")
def _probe() -> list[Finding]:
    findings: list[Finding] = []

    split = split_payment(
        Money.of("999.99", "USD"),
        [
            SellerLine("a", Money.of("333.33", "USD"), Fraction(7, 100)),
            SellerLine("b", Money.of("333.33", "USD"), Fraction(11, 100)),
            SellerLine("c", Money.of("333.33", "USD"), Fraction(13, 100)),
        ],
    )
    findings.append(Finding("a marketplace split reconciles", split.reconciles(), True))

    run = AllocationRun("USD")
    for index in range(7):
        centre = run.add_centre(CostCentre(f"C{index}", f"Centre {index}"))
        centre.set_driver("headcount", Fraction(index + 1))
    run.add_pool(CostPool("Overhead", AWKWARD, "headcount"))
    run.run()
    findings.append(Finding("an overhead pool allocates whole", run.is_complete(), True))

    contract = MilestoneContract("M-1", AWKWARD)
    contract.define([("design", 2), ("build", 5), ("handover", 3)])
    findings.append(
        Finding(
            "milestones sum to the contract",
            contract.milestones_sum_to_contract(),
            True,
        )
    )

    revenue = RevenueContract("R-1", AWKWARD, DAY)
    revenue.add(Obligation("device", Money.of(600, "USD")))
    revenue.add(Obligation("service", Money.of(500, "USD")))
    revenue.add(Obligation("install", Money.of(100, "USD")))
    revenue.allocate_price()
    findings.append(
        Finding("revenue allocates to the price", revenue.allocation_sums_to_price(), True)
    )

    register = ShareRegister()
    for name, shares in (("a", 7), ("b", 11), ("c", 13)):
        register.add(name, shares, DAY)
    dividend = declare("D-1", AWKWARD, Money.of(999999, "USD"), DAY, DAY, DAY)
    paid = _sum(amount for _, amount in dividend.allocate_to(register))
    findings.append(Finding("a dividend pays out the whole amount", paid, AWKWARD.units))

    plan = PaymentPlan("PL-1", AWKWARD)
    plan.build(7, DAY, 30)
    findings.append(Finding("a payment plan clears the debt", plan.covers_the_debt(), True))

    budget = phase(AWKWARD, DAY, Profile.WORKING_DAYS)
    findings.append(
        Finding("a phased budget sums to the annual", budget.sums_to_annual(), True)
    )

    mapping = ChartMapping("USD")
    mapping.map_many("OLD", [("A", Fraction(7)), ("B", Fraction(11)), ("C", Fraction(13))])
    findings.append(
        Finding(
            "a split chart mapping preserves the total",
            mapping.preserves_total({"OLD": AWKWARD}),
            True,
        )
    )
    return findings
