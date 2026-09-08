"""Insurance claims: the deductible, the limit, and the share in between.

An insured loss is rarely paid in full, and the three terms that
reduce it apply in a fixed order that policyholders routinely get
wrong. The deductible comes off first, since it is the part the
insured agreed to carry. Coinsurance then splits what remains, so
an eighty percent policy pays four fifths of the loss above the
deductible and not four fifths of the whole loss. The policy limit
caps the result, and it caps the insurer's payment rather than the
loss, which is the distinction that decides whether the limit
applies before or after the other two. Applying them in any other
order produces a different and wrong number, so this module fixes
the order and reports each step, letting a claims handler explain
the settlement rather than defend it. An aggregate limit across the
policy year is tracked as well, since a second claim after a large
first one may be capped by the year rather than by its own terms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


@dataclass(frozen=True)
class Policy:
    deductible: Money
    coinsurance: Fraction
    per_claim_limit: Money
    aggregate_limit: Money

    def __post_init__(self) -> None:
        for value in (self.coinsurance,):
            if value <= 0 or value > 1:
                raise Refused(
                    "a coinsurance share is above zero and at most one"
                )
        self.per_claim_limit.same_currency(self.deductible)
        self.aggregate_limit.same_currency(self.deductible)
        if self.deductible.is_negative():
            raise Refused("a deductible is not negative")
        if not self.per_claim_limit.is_positive():
            raise Refused("a per-claim limit is positive")
        if self.aggregate_limit < self.per_claim_limit:
            raise Refused(
                "an aggregate limit below the per-claim limit means the second "
                "figure can never be reached"
            )


@dataclass(frozen=True)
class Settlement:
    loss: Money
    after_deductible: Money
    after_coinsurance: Money
    payable: Money
    capped_by: str | None

    def insured_share(self) -> Money:
        return self.loss - self.payable

    def reconciles(self) -> bool:
        return self.payable + self.insured_share() == self.loss


@dataclass
class ClaimHistory:
    policy: Policy
    currency: str
    paid_to_date: Money | None = None
    settlements: list[Settlement] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.paid_to_date is None:
            self.paid_to_date = Money.zero(self.currency)

    def aggregate_remaining(self) -> Money:
        left = self.policy.aggregate_limit - self.paid_to_date
        return left if left.is_positive() else Money.zero(self.currency)

    def settle(self, loss: Money) -> Settlement:
        if loss.currency != self.currency:
            raise Refused(
                f"this policy covers {self.currency}, not {loss.currency}"
            )
        if not loss.is_positive():
            raise Refused("a claim is for a positive loss")

        # The order is fixed: deductible, then coinsurance, then the caps.
        above_deductible = loss - self.policy.deductible
        if above_deductible.is_negative():
            above_deductible = Money.zero(self.currency)
        shared = scale(above_deductible, self.policy.coinsurance, Rounding.HALF_EVEN)

        capped_by = None
        payable = shared
        if payable > self.policy.per_claim_limit:
            payable = self.policy.per_claim_limit
            capped_by = "the per-claim limit"
        if payable > self.aggregate_remaining():
            payable = self.aggregate_remaining()
            capped_by = "the aggregate limit for the year"

        settlement = Settlement(
            loss=loss,
            after_deductible=above_deductible,
            after_coinsurance=shared,
            payable=payable,
            capped_by=capped_by,
        )
        self.paid_to_date = self.paid_to_date + payable
        self.settlements.append(settlement)
        return settlement

    def total_paid(self) -> Money:
        return self.paid_to_date

    def total_losses(self) -> Money:
        total = Money.zero(self.currency)
        for settlement in self.settlements:
            total = total + settlement.loss
        return total

    def recovery_rate(self) -> Fraction | None:
        losses = self.total_losses()
        if losses.units == 0:
            return None
        return Fraction(self.paid_to_date.units, losses.units)

    def is_exhausted(self) -> bool:
        return self.aggregate_remaining().is_zero()
