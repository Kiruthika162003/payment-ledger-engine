"""Consignment: goods on your shelves that are not yours, and the sale that makes them so.

Consigned stock sits in the consignee's warehouse and belongs to
the consignor until it is sold. That single fact drives everything:
the consignee has no inventory asset and no purchase to record
while the goods sit there, and recognizes only a commission when
they sell, while the consignor keeps the inventory on its own books
even though it cannot see it. Getting this backwards inflates the
consignee's balance sheet with stock it does not own and its
revenue with sales that are somebody else's. This module tracks
consigned quantities on both sides and computes the settlement:
when the consignee sells, the consignor recognizes the sale and the
consignee recognizes its commission, and the goods leave the
consigned pool. Unsold goods can be returned at no cost to the
consignee, which is the whole appeal of the arrangement, and the
module refuses to sell or return more than is actually held,
because a consignment balance that goes negative means somebody has
lost track of physical goods.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


@dataclass(frozen=True)
class Shipment:
    date: datetime.date
    units: int
    unit_cost: Money


@dataclass(frozen=True)
class ConsignmentSale:
    date: datetime.date
    units: int
    unit_price: Money
    commission: Money
    consignor_proceeds: Money

    def gross(self) -> Money:
        return Money.from_minor(
            self.unit_price.units * self.units, self.unit_price.currency
        )

    def reconciles(self) -> bool:
        return self.commission + self.consignor_proceeds == self.gross()


@dataclass
class ConsignmentAccount:
    consignor: str
    consignee: str
    currency: str
    commission_rate: Fraction
    shipments: list[Shipment] = field(default_factory=list)
    sales: list[ConsignmentSale] = field(default_factory=list)
    returns: list[tuple[datetime.date, int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.commission_rate <= 0 or self.commission_rate >= 1:
            raise Refused("a consignment commission is a fraction below one")

    def ship(self, units: int, unit_cost: Money, on: datetime.date) -> Shipment:
        if unit_cost.currency != self.currency:
            raise Refused(
                f"this consignment is in {self.currency}, not {unit_cost.currency}"
            )
        if units < 1:
            raise Refused("a shipment sends at least one unit")
        if unit_cost.is_negative():
            raise Refused("a unit cost is not negative")
        shipment = Shipment(on, units, unit_cost)
        self.shipments.append(shipment)
        return shipment

    def units_shipped(self) -> int:
        return sum(item.units for item in self.shipments)

    def units_sold(self) -> int:
        return sum(item.units for item in self.sales)

    def units_returned(self) -> int:
        return sum(units for _, units in self.returns)

    def units_on_hand(self) -> int:
        return self.units_shipped() - self.units_sold() - self.units_returned()

    def consignee_inventory(self) -> Money:
        # Always nothing: the goods are on the shelves but not on the books.
        return Money.zero(self.currency)

    def consignor_inventory(self) -> Money:
        remaining = self.units_on_hand()
        if remaining == 0 or not self.shipments:
            return Money.zero(self.currency)
        total_units = self.units_shipped()
        total_value = sum(
            item.unit_cost.units * item.units for item in self.shipments
        )
        average = Fraction(total_value, total_units)
        return Money.from_minor(int(average * remaining), self.currency)

    def sell(
        self, units: int, unit_price: Money, on: datetime.date
    ) -> ConsignmentSale:
        if unit_price.currency != self.currency:
            raise Refused(
                f"this consignment is in {self.currency}, not {unit_price.currency}"
            )
        if units < 1:
            raise Refused("a sale moves at least one unit")
        if units > self.units_on_hand():
            raise Refused(
                f"a sale of {units} units exceeds the {self.units_on_hand()} held "
                "on consignment; a negative balance means physical goods are lost"
            )
        gross = Money.from_minor(unit_price.units * units, self.currency)
        commission = scale(gross, self.commission_rate, Rounding.HALF_EVEN)
        sale = ConsignmentSale(
            date=on,
            units=units,
            unit_price=unit_price,
            commission=commission,
            consignor_proceeds=gross - commission,
        )
        self.sales.append(sale)
        return sale

    def send_back(self, units: int, on: datetime.date) -> int:
        if units < 1:
            raise Refused("a return sends back at least one unit")
        if units > self.units_on_hand():
            raise Refused(
                f"a return of {units} units exceeds the {self.units_on_hand()} held"
            )
        self.returns.append((on, units))
        return self.units_on_hand()

    def consignee_revenue(self) -> Money:
        total = Money.zero(self.currency)
        for sale in self.sales:
            total = total + sale.commission
        return total

    def consignor_revenue(self) -> Money:
        total = Money.zero(self.currency)
        for sale in self.sales:
            total = total + sale.gross()
        return total

    def amount_due_to_consignor(self) -> Money:
        total = Money.zero(self.currency)
        for sale in self.sales:
            total = total + sale.consignor_proceeds
        return total
