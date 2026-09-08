"""Rolling reserves: the slice a processor withholds, and when it comes back.

A payment processor exposed to a merchant's future refunds and
chargebacks protects itself by holding back a percentage of each
settlement for a fixed period, a rolling reserve. The merchant sees
a smaller payout now and a stream of releases later, and the two
have to reconcile or the merchant is right to suspect they are
being shorted. This module computes the withholding on each
settlement and the releases due on a date, and the property it
maintains is that every dollar withheld is eventually released
exactly once: the reserve balance at any moment is the sum of
withholdings whose release date has not arrived, and once the last
release passes the balance is zero. Releases are dated by adding
the reserve period to the settlement date rather than by counting
from the merchant's first settlement, so each tranche matures on
its own schedule, which is what rolling means and what a naive
implementation with one global timer gets wrong. The reserve rate
must be a fraction below one, since withholding the entire
settlement is not a reserve, it is a freeze.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


@dataclass(frozen=True)
class Withholding:
    settlement_id: str
    settled_on: datetime.date
    gross: Money
    withheld: Money
    releases_on: datetime.date


@dataclass
class RollingReserve:
    rate: Fraction
    hold_days: int
    currency: str
    withholdings: list[Withholding] = field(default_factory=list)
    released: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.rate <= 0 or self.rate >= 1:
            raise Refused(
                "a reserve rate is a fraction below one; withholding the whole "
                "settlement is not a reserve, it is a freeze"
            )
        if self.hold_days < 1:
            raise Refused("a rolling reserve holds funds for at least a day")

    def withhold(
        self, settlement_id: str, gross: Money, on: datetime.date
    ) -> Withholding:
        if gross.currency != self.currency:
            raise Refused(
                f"this reserve is in {self.currency}, not {gross.currency}"
            )
        if not gross.is_positive():
            raise Refused("a settlement withheld against is positive")
        if any(w.settlement_id == settlement_id for w in self.withholdings):
            raise Refused(f"settlement {settlement_id!r} has already been withheld on")
        amount = scale(gross, self.rate, Rounding.HALF_EVEN)
        item = Withholding(
            settlement_id=settlement_id,
            settled_on=on,
            gross=gross,
            withheld=amount,
            releases_on=on + datetime.timedelta(days=self.hold_days),
        )
        self.withholdings.append(item)
        return item

    def payout_for(self, settlement_id: str) -> Money:
        item = self._find(settlement_id)
        return item.gross - item.withheld

    def due_for_release(self, as_of: datetime.date) -> list[Withholding]:
        return [
            item
            for item in self.withholdings
            if item.releases_on <= as_of and item.settlement_id not in self.released
        ]

    def release(self, as_of: datetime.date) -> Money:
        total = Money.zero(self.currency)
        for item in self.due_for_release(as_of):
            total = total + item.withheld
            self.released.add(item.settlement_id)
        return total

    def balance(self, as_of: datetime.date) -> Money:
        total = Money.zero(self.currency)
        for item in self.withholdings:
            if item.settlement_id in self.released:
                continue
            if item.releases_on > as_of:
                total = total + item.withheld
        return total

    def withheld_total(self) -> Money:
        total = Money.zero(self.currency)
        for item in self.withholdings:
            total = total + item.withheld
        return total

    def released_total(self) -> Money:
        total = Money.zero(self.currency)
        for item in self.withholdings:
            if item.settlement_id in self.released:
                total = total + item.withheld
        return total

    def _find(self, settlement_id: str) -> Withholding:
        for item in self.withholdings:
            if item.settlement_id == settlement_id:
                return item
        raise Refused(f"there is no withholding for settlement {settlement_id!r}")
