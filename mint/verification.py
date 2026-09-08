"""Verification tiers: what a customer may do depends on what they have proved.

Payment systems do not verify everyone to the same depth, because
full verification is expensive and slow and most customers only
want to move small amounts. So they tier: an unverified account can
do a little, a customer who has given an identity document can do
more, and one whose source of funds has been checked can do most
things. This module holds the tiers and the limits attached to
them, and answers the only question the payments path asks, whether
this customer may do this thing at this size. The limits are per
transaction and per rolling period, because the two catch different
abuses and a system with only one leaks through the other: a
per-transaction cap alone permits a thousand small transfers, and a
period cap alone permits one enormous one. Upgrading a tier is
recorded with the evidence that justified it, since a tier granted
without a recorded reason is indistinguishable from one granted by
mistake, and downgrades are supported because verification expires
and documents go stale.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.errors import Refused
from mint.money import Money


class Tier(Enum):
    UNVERIFIED = 0
    IDENTIFIED = 1
    VERIFIED = 2
    ENHANCED = 3


@dataclass(frozen=True)
class TierLimits:
    per_transaction: Money
    per_period: Money
    period_days: int

    def __post_init__(self) -> None:
        self.per_period.same_currency(self.per_transaction)
        if self.period_days < 1:
            raise Refused("a limit period spans at least one day")
        if self.per_transaction > self.per_period:
            raise Refused(
                "a per-transaction limit above the period limit is unreachable; "
                "one of the two is wrong"
            )


@dataclass(frozen=True)
class TierChange:
    at: datetime.date
    from_tier: Tier
    to_tier: Tier
    evidence: str


@dataclass
class CustomerProfile:
    customer_id: str
    currency: str
    tier: Tier = Tier.UNVERIFIED
    limits: dict[Tier, TierLimits] = field(default_factory=dict)
    history: list[TierChange] = field(default_factory=list)
    activity: list[tuple[datetime.date, Money]] = field(default_factory=list)

    def limits_now(self) -> TierLimits:
        if self.tier not in self.limits:
            raise Refused(
                f"no limits are defined for tier {self.tier.name}; a customer "
                "with no stated limits cannot be assessed"
            )
        return self.limits[self.tier]

    def spent_in_period(self, as_of: datetime.date) -> Money:
        window = self.limits_now().period_days
        cutoff = as_of - datetime.timedelta(days=window)
        total = Money.zero(self.currency)
        for date, amount in self.activity:
            if cutoff < date <= as_of:
                total = total + amount
        return total

    def may_transact(self, amount: Money, as_of: datetime.date) -> str | None:
        if amount.currency != self.currency:
            raise Refused(
                f"this profile is in {self.currency}, not {amount.currency}"
            )
        limits = self.limits_now()
        if amount > limits.per_transaction:
            return (
                f"{amount.format()} exceeds the "
                f"{limits.per_transaction.format()} single-transaction limit for "
                f"tier {self.tier.name}"
            )
        projected = self.spent_in_period(as_of) + amount
        if projected > limits.per_period:
            return (
                f"{projected.format()} would exceed the "
                f"{limits.per_period.format()} allowed over "
                f"{limits.period_days} days at tier {self.tier.name}"
            )
        return None

    def record(self, amount: Money, on: datetime.date) -> Money:
        blocked = self.may_transact(amount, on)
        if blocked is not None:
            raise Refused(blocked)
        self.activity.append((on, amount))
        return self.spent_in_period(on)

    def upgrade(self, to_tier: Tier, on: datetime.date, evidence: str) -> Tier:
        if to_tier.value <= self.tier.value:
            raise Refused(
                f"tier {to_tier.name} is not above {self.tier.name}; use a "
                "downgrade to move the other way"
            )
        if not evidence.strip():
            raise Refused(
                "an upgrade records the evidence that justified it; a tier "
                "granted without a reason cannot be told from one granted by "
                "mistake"
            )
        self.history.append(TierChange(on, self.tier, to_tier, evidence.strip()))
        self.tier = to_tier
        return self.tier

    def downgrade(self, to_tier: Tier, on: datetime.date, reason: str) -> Tier:
        if to_tier.value >= self.tier.value:
            raise Refused(f"tier {to_tier.name} is not below {self.tier.name}")
        if not reason.strip():
            raise Refused("a downgrade records why verification lapsed")
        self.history.append(TierChange(on, self.tier, to_tier, reason.strip()))
        self.tier = to_tier
        return self.tier


def standard_limits(currency: str = "USD") -> dict[Tier, TierLimits]:
    return {
        Tier.UNVERIFIED: TierLimits(
            Money.of(200, currency), Money.of(500, currency), 30
        ),
        Tier.IDENTIFIED: TierLimits(
            Money.of(2000, currency), Money.of(10000, currency), 30
        ),
        Tier.VERIFIED: TierLimits(
            Money.of(25000, currency), Money.of(100000, currency), 30
        ),
        Tier.ENHANCED: TierLimits(
            Money.of(250000, currency), Money.of(1000000, currency), 30
        ),
    }
