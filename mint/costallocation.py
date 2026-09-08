"""Allocating overheads: shared costs pushed onto the departments that caused them.

Rent, IT, and the finance team are real costs that no single
department incurred, and leaving them in a pool makes every
department look profitable while the business as a whole is not.
Allocation pushes them out on a driver, a measurable thing that
stands in for cause: floor area for rent, headcount for HR,
transactions for payments processing. The choice of driver is the
argument, and this module makes it explicit rather than hidden in a
spreadsheet formula. Two properties matter and are enforced. The
allocation must be complete, so every cent of the pool lands
somewhere, which the cent-conserving allocation guarantees. And a
department with no driver value must receive nothing rather than an
equal share, since giving a department with no headcount a share of
HR cost is exactly the arbitrary charge that makes managers stop
trusting the numbers. A pool whose drivers are all zero cannot be
allocated at all and is refused rather than spread evenly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import allocate


@dataclass(frozen=True)
class CostPool:
    name: str
    amount: Money
    driver: str

    def __post_init__(self) -> None:
        if not self.amount.is_positive():
            raise Refused(f"cost pool {self.name!r} holds a positive amount")
        if not self.driver.strip():
            raise Refused(f"cost pool {self.name!r} needs a driver to allocate on")


@dataclass
class CostCentre:
    code: str
    name: str
    drivers: dict[str, Fraction] = field(default_factory=dict)
    allocated: dict[str, int] = field(default_factory=dict)

    def set_driver(self, driver: str, value: Fraction) -> Fraction:
        if value < 0:
            raise Refused(f"driver {driver!r} cannot be negative")
        self.drivers[driver] = value
        return value

    def driver_value(self, driver: str) -> Fraction:
        return self.drivers.get(driver, Fraction(0))

    def total_allocated(self, currency: str) -> Money:
        return Money.from_minor(sum(self.allocated.values()), currency)


@dataclass
class AllocationRun:
    currency: str
    centres: list[CostCentre] = field(default_factory=list)
    pools: list[CostPool] = field(default_factory=list)

    def add_centre(self, centre: CostCentre) -> CostCentre:
        if any(existing.code == centre.code for existing in self.centres):
            raise Refused(f"cost centre {centre.code!r} is already in the run")
        self.centres.append(centre)
        return centre

    def add_pool(self, pool: CostPool) -> CostPool:
        if pool.amount.currency != self.currency:
            raise Refused(
                f"pool {pool.name!r} is in {pool.amount.currency}, not "
                f"{self.currency}"
            )
        self.pools.append(pool)
        return pool

    def eligible(self, driver: str) -> list[CostCentre]:
        # A centre with no driver value receives nothing rather than an equal
        # share, which is the arbitrary charge that loses managers' trust.
        return [
            centre for centre in self.centres if centre.driver_value(driver) > 0
        ]

    def allocate_pool(self, pool: CostPool) -> dict[str, Money]:
        recipients = self.eligible(pool.driver)
        if not recipients:
            raise Refused(
                f"no cost centre has a value for driver {pool.driver!r}, so "
                f"pool {pool.name!r} cannot be allocated; spreading it evenly "
                "would be an arbitrary charge"
            )
        weights = [centre.driver_value(pool.driver) for centre in recipients]
        shares = allocate(pool.amount, weights)
        result: dict[str, Money] = {}
        for centre, share in zip(recipients, shares, strict=True):
            centre.allocated[pool.name] = (
                centre.allocated.get(pool.name, 0) + share.units
            )
            result[centre.code] = share
        return result

    def run(self) -> dict[str, Money]:
        for pool in self.pools:
            self.allocate_pool(pool)
        return {
            centre.code: centre.total_allocated(self.currency)
            for centre in self.centres
        }

    def pool_total(self) -> Money:
        total = Money.zero(self.currency)
        for pool in self.pools:
            total = total + pool.amount
        return total

    def allocated_total(self) -> Money:
        total = Money.zero(self.currency)
        for centre in self.centres:
            total = total + centre.total_allocated(self.currency)
        return total

    def is_complete(self) -> bool:
        return self.allocated_total() == self.pool_total()

    def share_of(self, code: str) -> Fraction | None:
        total = self.allocated_total()
        if total.units == 0:
            return None
        for centre in self.centres:
            if centre.code == code:
                return Fraction(
                    centre.total_allocated(self.currency).units, total.units
                )
        raise Refused(f"there is no cost centre {code!r} in this run")
