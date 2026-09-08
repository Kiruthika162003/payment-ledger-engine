"""Inventory costing: which units you sold decides what the profit was.

Physical goods are interchangeable but their costs are not, so when
prices move, the cost of a sale depends entirely on which purchase
lot the sale is deemed to draw from. First in first out costs a sale
at the oldest lot's price, which leaves the newest and usually
dearest costs on the balance sheet. Last in first out does the
reverse, costing at the newest price and leaving old cheap costs in
inventory, which in a rising market reports lower profit and lower
tax. Weighted average blends every lot into one running cost, so a
late expensive purchase raises the cost of goods sold immediately
rather than waiting for the old lots to be consumed. This module
implements all three from the same lot history so they can be
compared on identical data, which is the only way to see that the
difference is a choice of method rather than a fact about the
goods. Selling more units than are held is refused, since negative
inventory is not a cheaper way to trade, and the module reports
both the cost of goods sold and the value of what remains so the
two always add back to what was bought.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


class CostMethod(Enum):
    FIFO = "fifo"
    LIFO = "lifo"
    WEIGHTED_AVERAGE = "weighted_average"


@dataclass
class Lot:
    quantity: int
    unit_cost: Money


@dataclass
class Inventory:
    currency: str
    method: CostMethod
    lots: list[Lot] = field(default_factory=list)
    purchased_value: Money | None = None
    cost_of_goods_sold: Money | None = None
    pool_quantity: int = 0
    pool_value: int = 0

    def __post_init__(self) -> None:
        zero = Money.zero(self.currency)
        self.purchased_value = self.purchased_value or zero
        self.cost_of_goods_sold = self.cost_of_goods_sold or zero

    def _is_pooled(self) -> bool:
        # Weighted average keeps one pool rather than lots, because costing a
        # sale at the blend while valuing the remainder at original lot costs
        # leaves the two sides unable to reconcile.
        return self.method is CostMethod.WEIGHTED_AVERAGE

    def on_hand(self) -> int:
        if self._is_pooled():
            return self.pool_quantity
        return sum(lot.quantity for lot in self.lots)

    def purchase(self, quantity: int, unit_cost: Money) -> int:
        if quantity < 1:
            raise Refused("a purchase brings in at least one unit")
        if unit_cost.currency != self.currency:
            raise Refused(
                f"this inventory is costed in {self.currency}, not {unit_cost.currency}"
            )
        if unit_cost.is_negative():
            raise Refused("a unit cost is not negative")
        if self._is_pooled():
            self.pool_quantity += quantity
            self.pool_value += unit_cost.units * quantity
        else:
            self.lots.append(Lot(quantity, unit_cost))
        self.purchased_value = self.purchased_value + Money.from_minor(
            unit_cost.units * quantity, self.currency
        )
        return self.on_hand()

    def average_cost(self) -> Fraction:
        held = self.on_hand()
        if held == 0:
            return Fraction(0)
        if self._is_pooled():
            return Fraction(self.pool_value, held)
        total = sum(lot.unit_cost.units * lot.quantity for lot in self.lots)
        return Fraction(total, held)

    def sell(self, quantity: int) -> Money:
        if quantity < 1:
            raise Refused("a sale takes at least one unit")
        if quantity > self.on_hand():
            raise Refused(
                f"a sale of {quantity} units exceeds the {self.on_hand()} on "
                "hand; negative inventory is not a cheaper way to trade"
            )
        if self.method is CostMethod.WEIGHTED_AVERAGE:
            cost = self._sell_average(quantity)
        else:
            cost = self._sell_lots(quantity)
        self.cost_of_goods_sold = self.cost_of_goods_sold + cost
        return cost

    def _sell_average(self, quantity: int) -> Money:
        average = self.average_cost()
        cost = round_money(average * quantity, self.currency, Rounding.HALF_EVEN)
        # The pool loses exactly what the sale was costed at, so the value
        # still held always equals what was bought less what was sold.
        self.pool_quantity -= quantity
        self.pool_value -= cost.units
        return cost

    def _sell_lots(self, quantity: int) -> Money:
        cost = Money.zero(self.currency)
        remaining = quantity
        while remaining > 0:
            index = 0 if self.method is CostMethod.FIFO else len(self.lots) - 1
            lot = self.lots[index]
            take = min(remaining, lot.quantity)
            cost = cost + Money.from_minor(lot.unit_cost.units * take, self.currency)
            lot.quantity -= take
            remaining -= take
            if lot.quantity == 0:
                self.lots.pop(index)
        return cost

    def closing_value(self) -> Money:
        if self._is_pooled():
            return Money.from_minor(self.pool_value, self.currency)
        total = sum(lot.unit_cost.units * lot.quantity for lot in self.lots)
        return Money.from_minor(total, self.currency)

    def reconciles(self) -> bool:
        # What was bought equals what was sold plus what is still held, up to
        # the rounding the average method necessarily introduces.
        difference = (
            self.purchased_value - self.cost_of_goods_sold - self.closing_value()
        )
        return abs(difference.units) <= 1
