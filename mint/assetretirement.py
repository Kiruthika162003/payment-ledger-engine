"""Decommissioning: the cost of taking something down, recognized when it goes up.

A business that builds an oil platform, a mine, or a nuclear plant
takes on an obligation to dismantle it decades later, and that
obligation exists from the day construction finishes rather than
from the day the work starts. The accounting is unusual and worth
stating: the present value of the future decommissioning cost is
recognized as a liability immediately and, unlike almost every
other provision, the matching debit is not an expense but an
addition to the asset itself. The cost of the platform therefore
includes the cost of removing it, and that combined figure
depreciates over the platform's life, which is what spreads the
removal cost across the years that benefited from the asset. The
liability then unwinds as a finance cost while the asset
depreciates as an operating one, so the same obligation shows up in
two different places for two different reasons. This module carries
both sides and keeps them consistent, since a revision to the
estimate adjusts the asset rather than hitting profit at once.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.provisiondiscount import DiscountedProvision
from mint.rounding import Rounding, round_money


@dataclass
class RetirementObligation:
    id: str
    asset_construction_cost: Money
    estimated_removal_cost: Money
    rate: Fraction
    life_years: int
    provision: DiscountedProvision | None = None
    accumulated_depreciation: Money | None = None
    years_depreciated: int = 0

    def __post_init__(self) -> None:
        self.estimated_removal_cost.same_currency(self.asset_construction_cost)
        if not self.asset_construction_cost.is_positive():
            raise Refused("an asset is built for a positive cost")
        if not self.estimated_removal_cost.is_positive():
            raise Refused("a decommissioning estimate is positive")
        if self.life_years < 1:
            raise Refused("an asset's life is at least one year")
        if self.provision is None:
            self.provision = DiscountedProvision(
                id=f"{self.id}-provision",
                undiscounted=self.estimated_removal_cost,
                rate=self.rate,
                periods=self.life_years,
            )
        if self.accumulated_depreciation is None:
            self.accumulated_depreciation = Money.zero(
                self.asset_construction_cost.currency
            )

    def capitalized_cost(self) -> Money:
        # The unusual bit: the debit is added to the asset, not expensed, so
        # the cost of the platform includes the cost of removing it.
        return self.asset_construction_cost + self.provision.present_value()

    def annual_depreciation(self) -> Money:
        return round_money(
            Fraction(self.capitalized_cost().units, self.life_years),
            self.asset_construction_cost.currency,
            Rounding.HALF_EVEN,
        )

    def carrying_value(self) -> Money:
        return self.capitalized_cost() - self.accumulated_depreciation

    def liability(self) -> Money:
        return self.provision.carrying

    def depreciate(self) -> Money:
        if self.is_fully_depreciated():
            raise Refused(f"asset {self.id!r} is already fully depreciated")
        remaining = self.capitalized_cost() - self.accumulated_depreciation
        self.years_depreciated += 1
        if self.years_depreciated >= self.life_years:
            # The last year takes exactly what is left. Ten rounded annual
            # charges do not sum to the capitalized cost, and without this the
            # asset finishes a few cents short of fully written down.
            charge = remaining
        else:
            charge = min(self.annual_depreciation(), remaining)
        self.accumulated_depreciation = self.accumulated_depreciation + charge
        return charge

    def unwind(self) -> Money:
        return self.provision.unwind()

    def advance_year(self) -> tuple[Money, Money]:
        # Two lines for the same obligation: operating and financing.
        return self.depreciate(), self.unwind()

    def is_fully_depreciated(self) -> bool:
        return self.accumulated_depreciation >= self.capitalized_cost()

    def is_ready_for_removal(self) -> bool:
        return self.provision.is_fully_unwound()

    def liability_at_removal(self) -> Money:
        return self.estimated_removal_cost

    def revise_estimate(self, new_estimate: Money) -> Money:
        new_estimate.same_currency(self.estimated_removal_cost)
        if not new_estimate.is_positive():
            raise Refused("a revised decommissioning estimate stays positive")
        # Adjusts the asset rather than hitting profit at once.
        movement = self.provision.remeasure(undiscounted=new_estimate)
        self.estimated_removal_cost = new_estimate
        return movement

    def total_charged_to_date(self) -> Money:
        return self.accumulated_depreciation + self.provision.total_finance_cost()
