"""The asset register: what was bought, what it is worth now, and what disposal realized.

A fixed asset lives on the books for years, and the register is the
record that keeps its three numbers straight: the cost it was
bought for, the depreciation accumulated against it, and the
difference between them, the carrying value. Confusing carrying
value with cost is how an asset sold for less than it cost is
booked as a loss when it was actually a gain, because after years
of depreciation the book no longer expects the asset to be worth
what it cost. This module holds the register and computes disposal
correctly: the gain or loss is the proceeds less the carrying
value, not less the original cost, and it is reported with both
figures so the arithmetic is visible. Depreciation is charged
period by period rather than derived on demand, so the register
knows how much has actually been recognized and a disposal partway
through a life uses the depreciation charged, not the depreciation
that would eventually have been. A disposed asset stays in the
register marked as disposed, because removing it would erase the
history that explains the gain.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.depreciation import straight_line
from mint.errors import Refused
from mint.money import Money


@dataclass
class FixedAsset:
    id: str
    description: str
    cost: Money
    acquired: datetime.date
    life_years: int
    salvage: Money
    accumulated: Money | None = None
    disposed_on: datetime.date | None = None
    proceeds: Money | None = None

    def __post_init__(self) -> None:
        self.salvage.same_currency(self.cost)
        if not self.cost.is_positive():
            raise Refused("an asset is acquired for a positive cost")
        if self.life_years < 1:
            raise Refused("an asset's useful life is at least one year")
        if self.salvage > self.cost:
            raise Refused("an asset cannot be worth more scrapped than bought")
        if self.accumulated is None:
            self.accumulated = Money.zero(self.cost.currency)

    def carrying_value(self) -> Money:
        return self.cost - self.accumulated

    def depreciable_base(self) -> Money:
        return self.cost - self.salvage

    def is_disposed(self) -> bool:
        return self.disposed_on is not None

    def is_fully_depreciated(self) -> bool:
        return self.accumulated >= self.depreciable_base()

    def annual_charge(self) -> Money:
        return Money.from_minor(
            straight_line(self.cost, self.salvage, self.life_years).rows[0].depreciation,
            self.cost.currency,
        )

    def depreciate(self, amount: Money | None = None) -> Money:
        if self.is_disposed():
            raise Refused(f"asset {self.id!r} is disposed and no longer depreciates")
        charge = amount if amount is not None else self.annual_charge()
        charge.same_currency(self.cost)
        if not charge.is_positive():
            raise Refused("a depreciation charge is positive")
        remaining = self.depreciable_base() - self.accumulated
        # Never past salvage: the last charge takes exactly what is left.
        charge = min(charge, remaining)
        if charge.is_zero():
            raise Refused(
                f"asset {self.id!r} is already fully depreciated to its salvage "
                "value"
            )
        self.accumulated = self.accumulated + charge
        return charge

    def dispose(self, proceeds: Money, on: datetime.date) -> Money:
        if self.is_disposed():
            raise Refused(f"asset {self.id!r} was already disposed")
        proceeds.same_currency(self.cost)
        if proceeds.is_negative():
            raise Refused("disposal proceeds are not negative")
        if on < self.acquired:
            raise Refused("an asset cannot be disposed before it was acquired")
        self.disposed_on = on
        self.proceeds = proceeds
        # Against carrying value, not cost: the book stopped expecting the
        # asset to be worth what it cost years ago.
        return proceeds - self.carrying_value()

    def gain_on_disposal(self) -> Money:
        if not self.is_disposed():
            raise Refused(f"asset {self.id!r} has not been disposed")
        return self.proceeds - self.carrying_value()


@dataclass
class AssetRegister:
    currency: str
    assets: list[FixedAsset] = field(default_factory=list)

    def add(self, asset: FixedAsset) -> FixedAsset:
        if asset.cost.currency != self.currency:
            raise Refused(
                f"asset {asset.id!r} is costed in {asset.cost.currency}, not "
                f"the register currency {self.currency}"
            )
        if any(existing.id == asset.id for existing in self.assets):
            raise Refused(f"asset {asset.id!r} is already in the register")
        self.assets.append(asset)
        return asset

    def get(self, asset_id: str) -> FixedAsset:
        for asset in self.assets:
            if asset.id == asset_id:
                return asset
        raise Refused(f"there is no asset {asset_id!r} in the register")

    def active(self) -> list[FixedAsset]:
        return [asset for asset in self.assets if not asset.is_disposed()]

    def total_cost(self) -> Money:
        total = Money.zero(self.currency)
        for asset in self.active():
            total = total + asset.cost
        return total

    def total_accumulated(self) -> Money:
        total = Money.zero(self.currency)
        for asset in self.active():
            total = total + asset.accumulated
        return total

    def net_book_value(self) -> Money:
        return self.total_cost() - self.total_accumulated()

    def charge_all(self) -> Money:
        total = Money.zero(self.currency)
        for asset in self.active():
            if not asset.is_fully_depreciated():
                total = total + asset.depreciate()
        return total
