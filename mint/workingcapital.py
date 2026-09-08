"""The cash conversion cycle: how many days the business funds itself.

Between paying a supplier and being paid by a customer, a business
funds the gap out of its own pocket, and the length of that gap is
the cash conversion cycle. It is three numbers. Days sales
outstanding is how long customers take to pay. Days inventory
outstanding is how long stock sits before it sells. Days payable
outstanding is how long the business itself takes to pay
suppliers, and it is subtracted, because supplier credit funds part
of the gap. A business can be profitable and still fail on this
number alone, which is why it belongs beside the income statement
rather than in a footnote. This module computes all three from the
balances and flows rather than from separately maintained metrics,
so they cannot disagree with the accounts. Each ratio divides by a
flow that can legitimately be zero, a business with no sales in the
period has no meaningful days-sales figure, so each returns nothing
rather than an infinity that a dashboard would render as a very
large and very wrong number.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class WorkingCapital:
    receivables: Money
    inventory: Money
    payables: Money
    revenue: Money
    cost_of_sales: Money
    days_in_period: int = 365

    def __post_init__(self) -> None:
        base = self.receivables.currency
        for value in (self.inventory, self.payables, self.revenue, self.cost_of_sales):
            if value.currency != base:
                raise Refused("a working capital set is in one currency")
        if self.days_in_period < 1:
            raise Refused("a period spans at least one day")
        for value in (self.receivables, self.inventory, self.payables):
            if value.is_negative():
                raise Refused("a working capital balance is not negative")

    def days_sales_outstanding(self) -> Fraction | None:
        if self.revenue.units == 0:
            return None
        return Fraction(self.receivables.units * self.days_in_period, self.revenue.units)

    def days_inventory_outstanding(self) -> Fraction | None:
        if self.cost_of_sales.units == 0:
            return None
        return Fraction(
            self.inventory.units * self.days_in_period, self.cost_of_sales.units
        )

    def days_payable_outstanding(self) -> Fraction | None:
        if self.cost_of_sales.units == 0:
            return None
        return Fraction(
            self.payables.units * self.days_in_period, self.cost_of_sales.units
        )

    def cash_conversion_cycle(self) -> Fraction | None:
        parts = (
            self.days_sales_outstanding(),
            self.days_inventory_outstanding(),
            self.days_payable_outstanding(),
        )
        if any(part is None for part in parts):
            return None
        sales, inventory, payable = parts
        return sales + inventory - payable

    def is_self_funding(self) -> bool:
        # A negative cycle means suppliers fund the business entirely.
        cycle = self.cash_conversion_cycle()
        return cycle is not None and cycle <= 0

    def working_capital(self) -> Money:
        return self.receivables + self.inventory - self.payables

    def funding_gap(self) -> Money | None:
        cycle = self.cash_conversion_cycle()
        if cycle is None or self.revenue.units == 0:
            return None
        daily_revenue = Fraction(self.revenue.units, self.days_in_period)
        return Money.from_minor(
            int(daily_revenue * cycle), self.receivables.currency
        )

    def verdict(self) -> str:
        cycle = self.cash_conversion_cycle()
        if cycle is None:
            return "not enough activity to measure a cycle"
        if cycle <= 0:
            return "suppliers fund the whole cycle"
        if cycle <= 30:
            return "a short cycle, funded for about a month"
        if cycle <= 90:
            return "a normal cycle for a trading business"
        return "a long cycle; the business funds itself for a quarter or more"


def improvement(before: WorkingCapital, after: WorkingCapital) -> Fraction | None:
    first = before.cash_conversion_cycle()
    second = after.cash_conversion_cycle()
    if first is None or second is None:
        return None
    return first - second
