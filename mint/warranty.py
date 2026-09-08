"""Warranty provisions: estimating repairs not yet claimed, from the rate they actually arrive.

A business that sells goods with a warranty owes money it does not
yet know about: some fraction of what it sold will come back to be
repaired. That obligation exists the moment the sale happens, not
the moment the claim arrives, so it belongs in the period of the
sale, which is what a warranty provision is for. The estimate comes
from history rather than optimism: the claim rate observed on past
cohorts and the average cost of a claim, both measured rather than
assumed. This module holds the provision and, more usefully, the
comparison that keeps it honest, which is the provision made
against the claims actually paid. A provision that is consistently
too small means the estimate is wrong and the business is
reporting profit it will later give back; one consistently too
large means the reverse. So the module reports utilization, the
share of the provision consumed, and flags the two failure
directions by name rather than leaving a reader to compare two
numbers and guess which way is bad.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


@dataclass(frozen=True)
class ClaimHistory:
    units_sold: int
    claims_made: int
    total_claim_cost: Money

    def __post_init__(self) -> None:
        if self.units_sold < 1:
            raise Refused("a claim history covers at least one unit sold")
        if self.claims_made < 0:
            raise Refused("a claim count is not negative")
        if self.claims_made > self.units_sold:
            raise Refused(
                "more claims than units sold; the history covers the wrong "
                "population"
            )

    def claim_rate(self) -> Fraction:
        return Fraction(self.claims_made, self.units_sold)

    def average_claim_cost(self) -> Money:
        if self.claims_made == 0:
            return Money.zero(self.total_claim_cost.currency)
        return round_money(
            Fraction(self.total_claim_cost.units, self.claims_made),
            self.total_claim_cost.currency,
            Rounding.HALF_EVEN,
        )

    def cost_per_unit_sold(self) -> Fraction:
        return Fraction(self.total_claim_cost.units, self.units_sold)


@dataclass
class WarrantyProvision:
    currency: str
    history: ClaimHistory
    units_sold_this_period: int = 0
    provided: Money | None = None
    claims_paid: Money | None = None
    claim_count: int = 0

    def __post_init__(self) -> None:
        if self.history.total_claim_cost.currency != self.currency:
            raise Refused(
                f"this provision is in {self.currency} but the history is in "
                f"{self.history.total_claim_cost.currency}"
            )
        zero = Money.zero(self.currency)
        self.provided = self.provided or zero
        self.claims_paid = self.claims_paid or zero

    def sell(self, units: int) -> int:
        if units < 1:
            raise Refused("a sale covers at least one unit")
        self.units_sold_this_period += units
        return self.units_sold_this_period

    def required_provision(self) -> Money:
        return round_money(
            self.history.cost_per_unit_sold() * self.units_sold_this_period,
            self.currency,
            Rounding.HALF_EVEN,
        )

    def movement(self) -> Money:
        return self.required_provision() - self.provided

    def post_provision(self) -> Money:
        movement = self.movement()
        self.provided = self.required_provision()
        return movement

    def pay_claim(self, amount: Money) -> Money:
        amount.same_currency(Money.zero(self.currency))
        if not amount.is_positive():
            raise Refused("a warranty claim costs a positive amount")
        self.claims_paid = self.claims_paid + amount
        self.claim_count += 1
        return self.remaining()

    def remaining(self) -> Money:
        return self.provided - self.claims_paid

    def utilization(self) -> Fraction | None:
        if self.provided.units == 0:
            return None
        return Fraction(self.claims_paid.units, self.provided.units)

    def verdict(self) -> str:
        used = self.utilization()
        if used is None:
            return "nothing provided yet"
        if used > 1:
            return (
                "under-provided; the estimate is too low and profit reported "
                "earlier will be given back"
            )
        if used < Fraction(1, 2):
            return "over-provided; the estimate looks too high"
        return "the provision is tracking the claims"

    def is_under_provided(self) -> bool:
        return self.remaining().is_negative()
