"""Tax jurisdictions: stacking state, county, and city rates into one charge.

In places where sales tax is levied by several overlapping
authorities, the rate at an address is the sum of every
jurisdiction covering it, and the arithmetic is less obvious than
it looks. The rates stack additively on the same base by default,
so a state at six and a county at one and a city at half a percent
is seven and a half percent of the net, and computing the tax as
one combined rate is not the same as computing three roundings and
adding them. This module computes the combined rate first and
rounds once, because rounding per jurisdiction and summing can
produce a total a cent different from the rate a customer sees on
the receipt, and the receipt is what gets disputed. It still
reports the per-jurisdiction breakdown, which the remittance
requires, by allocating the single rounded total across the
jurisdictions in proportion to their rates using the
cent-conserving allocation, so the parts remitted always sum to the
tax collected. A jurisdiction may be marked exempt for a
transaction, which removes it from both the rate and the
breakdown rather than charging zero and leaving a confusing line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, allocate, scale


@dataclass(frozen=True)
class Jurisdiction:
    name: str
    level: str
    rate: Fraction

    def __post_init__(self) -> None:
        if self.rate < 0:
            raise Refused(f"jurisdiction {self.name!r} has a negative rate")


@dataclass
class TaxAddress:
    label: str
    jurisdictions: list[Jurisdiction] = field(default_factory=list)
    exempt: set[str] = field(default_factory=set)

    def add(self, jurisdiction: Jurisdiction) -> Jurisdiction:
        if any(j.name == jurisdiction.name for j in self.jurisdictions):
            raise Refused(
                f"jurisdiction {jurisdiction.name!r} is already on address "
                f"{self.label!r}"
            )
        self.jurisdictions.append(jurisdiction)
        return jurisdiction

    def exempt_from(self, name: str) -> None:
        if not any(j.name == name for j in self.jurisdictions):
            raise Refused(f"address {self.label!r} has no jurisdiction {name!r}")
        self.exempt.add(name)

    def active(self) -> list[Jurisdiction]:
        return [j for j in self.jurisdictions if j.name not in self.exempt]

    def combined_rate(self) -> Fraction:
        total = Fraction(0)
        for jurisdiction in self.active():
            total += jurisdiction.rate
        return total

    def tax_on(self, net: Money, mode: Rounding = Rounding.HALF_EVEN) -> Money:
        # One rounding on the combined rate, so the total matches the rate
        # printed on the receipt rather than a sum of per-level roundings.
        return scale(net, self.combined_rate(), mode)

    def breakdown(self, net: Money) -> list[tuple[str, Money]]:
        active = self.active()
        if not active:
            return []
        total = self.tax_on(net)
        if total.is_zero():
            return [(j.name, Money.zero(net.currency)) for j in active]
        weights = [j.rate for j in active]
        if sum(weights, Fraction(0)) == 0:
            return [(j.name, Money.zero(net.currency)) for j in active]
        shares = allocate(total, weights)
        return list(zip([j.name for j in active], shares, strict=True))

    def breakdown_reconciles(self, net: Money) -> bool:
        parts = self.breakdown(net)
        total = Money.zero(net.currency)
        for _, amount in parts:
            total = total + amount
        return total == self.tax_on(net)
