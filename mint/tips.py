"""Tips and service charges: whose money it is, and how a pool is shared out.

A tip and a service charge look identical on a bill and are
different things in law. A tip is voluntary and belongs to the
staff; a service charge is a mandatory part of the price, belongs to
the business, and is revenue on which tax is due. Treating a
service charge as a tip understates revenue and the tax on it,
while treating a tip as revenue takes money that was never the
employer's, which is the abuse that made tipping law strict. This
module keeps them apart from the moment they are recorded. Pooled
tips are shared by hours worked, or by weighted role where a
kitchen shares at a different rate from the floor, and the
distribution conserves the cent so what is collected is what is
paid out. An employer deduction from a tip pool is refused unless
it is a permitted one and recorded as such, because the default has
to be that the pool belongs entirely to the people who earned it.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import allocate


class Gratuity(Enum):
    TIP = "tip"
    SERVICE_CHARGE = "service_charge"


@dataclass(frozen=True)
class Receipt:
    date: datetime.date
    amount: Money
    kind: Gratuity

    def belongs_to_staff(self) -> bool:
        return self.kind is Gratuity.TIP

    def is_revenue(self) -> bool:
        return self.kind is Gratuity.SERVICE_CHARGE


@dataclass(frozen=True)
class Worker:
    name: str
    hours: Fraction
    role_weight: Fraction = Fraction(1)

    def __post_init__(self) -> None:
        if self.hours <= 0:
            raise Refused(f"{self.name!r} worked no hours to share on")
        if self.role_weight <= 0:
            raise Refused(f"{self.name!r} needs a positive role weight")

    def share_weight(self) -> Fraction:
        return self.hours * self.role_weight


@dataclass
class TipPool:
    currency: str
    receipts: list[Receipt] = field(default_factory=list)
    workers: list[Worker] = field(default_factory=list)
    deductions: list[tuple[str, Money]] = field(default_factory=list)
    permitted_deductions: frozenset[str] = frozenset({"card processing"})

    def record(self, amount: Money, on: datetime.date, kind: Gratuity) -> Receipt:
        if amount.currency != self.currency:
            raise Refused(
                f"this pool is in {self.currency}, not {amount.currency}"
            )
        if not amount.is_positive():
            raise Refused("a gratuity is a positive amount")
        receipt = Receipt(on, amount, kind)
        self.receipts.append(receipt)
        return receipt

    def add_worker(self, worker: Worker) -> Worker:
        if any(existing.name == worker.name for existing in self.workers):
            raise Refused(f"{worker.name!r} is already in the pool")
        self.workers.append(worker)
        return worker

    def tips_collected(self) -> Money:
        total = Money.zero(self.currency)
        for receipt in self.receipts:
            if receipt.belongs_to_staff():
                total = total + receipt.amount
        return total

    def service_charge_revenue(self) -> Money:
        # The employer's money, and taxable; never mixed into the pool.
        total = Money.zero(self.currency)
        for receipt in self.receipts:
            if receipt.is_revenue():
                total = total + receipt.amount
        return total

    def deduct(self, reason: str, amount: Money) -> Money:
        amount.same_currency(Money.zero(self.currency))
        if reason not in self.permitted_deductions:
            raise Refused(
                f"{reason!r} is not a permitted deduction from a tip pool; the "
                "pool belongs to the people who earned it unless the law says "
                "otherwise"
            )
        if not amount.is_positive():
            raise Refused("a deduction is a positive amount")
        if amount > self.distributable():
            raise Refused("a deduction cannot exceed the pool")
        self.deductions.append((reason, amount))
        return self.distributable()

    def deducted_total(self) -> Money:
        total = Money.zero(self.currency)
        for _, amount in self.deductions:
            total = total + amount
        return total

    def distributable(self) -> Money:
        return self.tips_collected() - self.deducted_total()

    def distribution(self) -> list[tuple[str, Money]]:
        if not self.workers:
            raise Refused("a tip pool with no workers has nobody to pay")
        pool = self.distributable()
        if not pool.is_positive():
            return [(worker.name, Money.zero(self.currency)) for worker in self.workers]
        weights = [worker.share_weight() for worker in self.workers]
        shares = allocate(pool, weights)
        return [
            (worker.name, share)
            for worker, share in zip(self.workers, shares, strict=True)
        ]

    def distribution_is_complete(self) -> bool:
        total = Money.zero(self.currency)
        for _, share in self.distribution():
            total = total + share
        return total == self.distributable()

    def share_for(self, name: str) -> Money:
        for worker_name, share in self.distribution():
            if worker_name == name:
                return share
        raise Refused(f"{name!r} is not in this pool")
