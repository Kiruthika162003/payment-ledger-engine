"""Assay: the two tiered-pricing models really do charge differently.

Graduated and volume pricing are easy to confuse and easy to
implement as though they were the same thing, and the bug is
invisible because both produce plausible invoices. This assay pins
the difference with numbers: the same tier table and the same
quantity, priced both ways, must give two different totals, and the
graduated one must be the larger whenever a lower tier is cheaper
than a higher one is generous. It also measures the boundary, since
at exactly the tier threshold the two models agree and any
disagreement there means an off-by-one in which tier a quantity
falls into. The savings tiers in the savings module have the same
shape and the same trap, banded against whole-balance, so they are
measured here beside the pricing ones, because two modules
implementing the same distinction differently is how one of them
quietly drifts.
"""

from __future__ import annotations

from mint.assays.framework import Finding, assay
from mint.money import Money
from mint.pricing import PriceTable, PricingModel, Tier
from mint.savings import standard_banded, standard_whole_balance

TIERS = (
    Tier(up_to=100, unit_price=Money.from_minor(10, "USD")),
    Tier(up_to=None, unit_price=Money.from_minor(5, "USD")),
)


@assay("pricing", "do graduated and volume pricing genuinely differ")
def _probe() -> list[Finding]:
    findings: list[Finding] = []

    graduated = PriceTable(TIERS, PricingModel.GRADUATED)
    volume = PriceTable(TIERS, PricingModel.VOLUME)

    findings.append(Finding("graduated at 150 units", graduated.price(150).units, 1250))
    findings.append(Finding("volume at 150 units", volume.price(150).units, 750))
    findings.append(
        Finding(
            "the two models differ",
            graduated.price(150) != volume.price(150),
            True,
        )
    )

    # At the threshold exactly, both price everything in the first tier.
    findings.append(
        Finding(
            "they agree at the tier boundary",
            graduated.price(100).units == volume.price(100).units,
            True,
        )
    )
    findings.append(Finding("the boundary price", graduated.price(100).units, 1000))

    banded = standard_banded()
    whole = standard_whole_balance()
    balance = Money.of(15000, "USD")
    findings.append(
        Finding("banded interest at 15000", banded.annual_interest(balance).units, 25000)
    )
    findings.append(
        Finding("whole-balance interest at 15000", whole.annual_interest(balance).units, 45000)
    )
    findings.append(
        Finding(
            "the banded blend sits below the headline",
            banded.blended_rate(balance) < banded.headline_rate(),
            True,
        )
    )
    return findings
