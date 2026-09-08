"""Revenue contracts: splitting one price across the several things that were sold.

A contract that bundles a device, a year of service, and an
installation is one price for three promises, and revenue is
recognized as each promise is satisfied rather than when the money
arrives. The allocation is the hard part: the transaction price is
split across the obligations in proportion to what each would sell
for on its own, the standalone selling price, and not in proportion
to what the contract happens to list them at, because listing the
device at nearly the full price and the service at almost nothing
is how a bundle is used to pull revenue forward. This module
allocates on standalone prices with the cent conserved, so the
pieces sum to the contract exactly, and recognizes each obligation
only as it is satisfied, at a point in time or across a period. The
figure it reports beside recognized revenue is the contract
liability, what has been billed but not yet earned, which is the
number that tells a reader how much of the reported cash still has
work attached to it.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, allocate, scale


@dataclass
class Obligation:
    name: str
    standalone_price: Money
    over_time: bool = False
    allocated: Money | None = None
    satisfied: Fraction = Fraction(0)

    def __post_init__(self) -> None:
        if not self.standalone_price.is_positive():
            raise Refused(f"obligation {self.name!r} needs a positive standalone price")
        if self.satisfied < 0 or self.satisfied > 1:
            raise Refused("satisfaction runs from zero to one")

    def recognized(self) -> Money:
        if self.allocated is None:
            raise Refused(f"obligation {self.name!r} has no allocated price yet")
        return scale(self.allocated, self.satisfied, Rounding.HALF_EVEN)

    def unearned(self) -> Money:
        return self.allocated - self.recognized()

    def is_complete(self) -> bool:
        return self.satisfied == 1


@dataclass
class RevenueContract:
    id: str
    transaction_price: Money
    started: datetime.date
    obligations: list[Obligation] = field(default_factory=list)
    billed: Money | None = None

    def __post_init__(self) -> None:
        if not self.transaction_price.is_positive():
            raise Refused("a contract has a positive transaction price")
        if self.billed is None:
            self.billed = Money.zero(self.transaction_price.currency)

    def add(self, obligation: Obligation) -> Obligation:
        if obligation.standalone_price.currency != self.transaction_price.currency:
            raise Refused(
                f"obligation {obligation.name!r} is priced in "
                f"{obligation.standalone_price.currency}, not the contract "
                f"currency {self.transaction_price.currency}"
            )
        if any(existing.name == obligation.name for existing in self.obligations):
            raise Refused(f"obligation {obligation.name!r} is already on the contract")
        self.obligations.append(obligation)
        return obligation

    def allocate_price(self) -> dict[str, Money]:
        if not self.obligations:
            raise Refused("a contract needs at least one performance obligation")
        weights = [
            Fraction(item.standalone_price.units) for item in self.obligations
        ]
        # On standalone prices, not on what the contract listed them at, which
        # is how a bundle gets used to pull revenue forward.
        shares = allocate(self.transaction_price, weights)
        for obligation, share in zip(self.obligations, shares, strict=True):
            obligation.allocated = share
        return {item.name: item.allocated for item in self.obligations}

    def allocation_sums_to_price(self) -> bool:
        total = Money.zero(self.transaction_price.currency)
        for obligation in self.obligations:
            if obligation.allocated is None:
                return False
            total = total + obligation.allocated
        return total == self.transaction_price

    def get(self, name: str) -> Obligation:
        for obligation in self.obligations:
            if obligation.name == name:
                return obligation
        raise Refused(f"contract {self.id!r} has no obligation {name!r}")

    def satisfy(self, name: str, fraction: Fraction) -> Money:
        obligation = self.get(name)
        if fraction < 0 or fraction > 1:
            raise Refused("satisfaction runs from zero to one")
        if fraction < obligation.satisfied:
            raise Refused(
                f"obligation {name!r} cannot become less satisfied; revenue "
                "already recognized is not reversed by a progress estimate"
            )
        obligation.satisfied = fraction
        return obligation.recognized()

    def bill(self, amount: Money) -> Money:
        amount.same_currency(self.transaction_price)
        if not amount.is_positive():
            raise Refused("a billing is for a positive amount")
        if self.billed + amount > self.transaction_price:
            raise Refused(
                f"billing {amount.format()} would take the total billed past "
                f"the {self.transaction_price.format()} contract price"
            )
        self.billed = self.billed + amount
        return self.billed

    def recognized_revenue(self) -> Money:
        total = Money.zero(self.transaction_price.currency)
        for obligation in self.obligations:
            total = total + obligation.recognized()
        return total

    def contract_liability(self) -> Money:
        # Billed but not yet earned: how much reported cash still has work
        # attached to it.
        gap = self.billed - self.recognized_revenue()
        return gap if gap.is_positive() else Money.zero(self.transaction_price.currency)

    def contract_asset(self) -> Money:
        gap = self.recognized_revenue() - self.billed
        return gap if gap.is_positive() else Money.zero(self.transaction_price.currency)

    def is_complete(self) -> bool:
        return all(item.is_complete() for item in self.obligations)
