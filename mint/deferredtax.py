"""Deferred tax: the gap between the books and the tax return, and when it closes.

The books and the tax return disagree about when things count.
Depreciation is the usual example: the accounts spread an asset
over five years while the tax rules allow it all in the first, so
early on the tax return shows less profit than the accounts do. The
difference is temporary, because over the asset's life both add up
to the same total, and deferred tax is the entry that recognizes
the tax consequence now rather than letting it appear as a series
of unexplained swings in the effective rate. A temporary difference
where the books carry more than the tax base creates a deferred tax
liability, tax that will be paid later; the other direction creates
an asset, tax already paid that will come back. Permanent
differences, expenses the tax rules will never allow, are excluded
entirely, and the distinction matters: treating a permanent
difference as temporary books an asset that will never reverse.
Deferred tax is measured at the rate expected when it reverses, not
today's, which is why a rate change remeasures the whole balance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


@dataclass(frozen=True)
class TemporaryDifference:
    name: str
    carrying_amount: Money
    tax_base: Money
    is_asset_side: bool = True

    def __post_init__(self) -> None:
        self.tax_base.same_currency(self.carrying_amount)

    def difference(self) -> Money:
        return self.carrying_amount - self.tax_base

    def creates_liability(self) -> bool:
        # An asset carried above its tax base means tax deferred to later.
        if self.is_asset_side:
            return self.difference().is_positive()
        return self.difference().is_negative()

    def taxable_amount(self) -> Money:
        return self.difference() if self.is_asset_side else -self.difference()


@dataclass
class DeferredTaxAccount:
    currency: str
    tax_rate: Fraction
    differences: list[TemporaryDifference] = field(default_factory=list)
    recognized: Money | None = None

    def __post_init__(self) -> None:
        if self.tax_rate < 0 or self.tax_rate >= 1:
            raise Refused("a tax rate is a fraction below one")
        if self.recognized is None:
            self.recognized = Money.zero(self.currency)

    def add(self, difference: TemporaryDifference) -> TemporaryDifference:
        if difference.carrying_amount.currency != self.currency:
            raise Refused(
                f"difference {difference.name!r} is in "
                f"{difference.carrying_amount.currency}, not {self.currency}"
            )
        self.differences.append(difference)
        return difference

    def net_taxable_difference(self) -> Money:
        total = Money.zero(self.currency)
        for difference in self.differences:
            total = total + difference.taxable_amount()
        return total

    def required_balance(self) -> Money:
        return scale(self.net_taxable_difference(), self.tax_rate, Rounding.HALF_EVEN)

    def is_liability(self) -> bool:
        return self.required_balance().is_positive()

    def is_asset(self) -> bool:
        return self.required_balance().is_negative()

    def movement(self) -> Money:
        return self.required_balance() - self.recognized

    def post(self) -> Money:
        movement = self.movement()
        self.recognized = self.required_balance()
        return movement

    def remeasure(self, new_rate: Fraction) -> Money:
        # Deferred tax is measured at the rate expected when it reverses, so
        # a rate change restates the whole balance at once.
        if new_rate < 0 or new_rate >= 1:
            raise Refused("a tax rate is a fraction below one")
        before = self.required_balance()
        self.tax_rate = new_rate
        after = self.required_balance()
        return after - before

    def liability_side(self) -> list[TemporaryDifference]:
        return [item for item in self.differences if item.creates_liability()]


@dataclass(frozen=True)
class PermanentDifference:
    name: str
    amount: Money
    deductible: bool = False

    def affects_deferred_tax(self) -> bool:
        # Never: booking a permanent difference as deferred tax creates an
        # asset that will never reverse.
        return False
