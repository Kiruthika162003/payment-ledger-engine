"""The tax charge: reconciling the rate you should have paid to the rate you did.

A company's tax charge is almost never the headline rate times its
profit, and the reconciliation between the two is one of the most
read notes in any set of accounts because it is where the answer to
why did they pay so little lives. The reconciliation starts at
profit before tax multiplied by the statutory rate, then adds the
tax effect of expenses the rules will never allow, subtracts the
effect of income never taxed, adjusts for losses used or newly
recognized, and lands on the actual charge. This module builds that
walk and enforces the property that makes it worth publishing: the
adjustments must sum to the difference exactly, so a reconciliation
that does not foot is refused rather than printed with a plug line
called other. The effective rate is reported alongside, since that
is the number a reader compares against the statutory one, and the
charge is split between current tax, payable now, and deferred,
payable later, because a company with a low current charge and a
large deferred one has not avoided tax, it has postponed it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


@dataclass(frozen=True)
class ReconcilingItem:
    name: str
    tax_effect: Money


@dataclass
class TaxProvision:
    currency: str
    profit_before_tax: Money
    statutory_rate: Fraction
    current_tax: Money
    deferred_tax: Money
    items: list[ReconcilingItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.statutory_rate < 0 or self.statutory_rate >= 1:
            raise Refused("a statutory rate is a fraction below one")
        for value in (self.current_tax, self.deferred_tax):
            value.same_currency(self.profit_before_tax)

    def add(self, name: str, tax_effect: Money) -> ReconcilingItem:
        tax_effect.same_currency(self.profit_before_tax)
        if not name.strip():
            raise Refused("a reconciling item needs a name")
        item = ReconcilingItem(name.strip(), tax_effect)
        self.items.append(item)
        return item

    def tax_at_statutory_rate(self) -> Money:
        return scale(self.profit_before_tax, self.statutory_rate, Rounding.HALF_EVEN)

    def total_charge(self) -> Money:
        return self.current_tax + self.deferred_tax

    def adjustments(self) -> Money:
        total = Money.zero(self.currency)
        for item in self.items:
            total = total + item.tax_effect
        return total

    def unexplained(self) -> Money:
        expected = self.tax_at_statutory_rate() + self.adjustments()
        return self.total_charge() - expected

    def reconciles(self) -> bool:
        return self.unexplained().is_zero()

    def walk(self) -> list[tuple[str, int]]:
        if not self.reconciles():
            raise Refused(
                f"the reconciliation leaves {self.unexplained().format()} "
                "unexplained; name it as an item rather than printing a note "
                "with a plug line called other"
            )
        rows = [("tax at the statutory rate", self.tax_at_statutory_rate().units)]
        for item in self.items:
            rows.append((item.name, item.tax_effect.units))
        rows.append(("total tax charge", self.total_charge().units))
        return rows

    def effective_rate(self) -> Fraction | None:
        if self.profit_before_tax.units == 0:
            return None
        return Fraction(self.total_charge().units, self.profit_before_tax.units)

    def current_share(self) -> Fraction | None:
        if self.total_charge().units == 0:
            return None
        return Fraction(self.current_tax.units, self.total_charge().units)

    def is_mostly_deferred(self) -> bool:
        # Postponed rather than avoided, which is a different story.
        share = self.current_share()
        return share is not None and share < Fraction(1, 2)

    def close_with_item(self, name: str) -> ReconcilingItem:
        gap = self.unexplained()
        if gap.is_zero():
            raise Refused("the reconciliation already foots")
        return self.add(name, gap)
