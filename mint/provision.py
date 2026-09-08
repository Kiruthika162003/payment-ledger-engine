"""Bad debt provision: estimating what will not be collected, by how late it is.

Not every receivable is collected, and a balance sheet that
carries them all at face value overstates what the business owns.
The provision is the estimate of what will go bad, and the standard
method makes it a function of age, because the probability a
receivable is collected falls steeply the longer it sits: current
invoices almost all pay, ninety-day ones often do not. This module
applies a loss rate per aging bucket to the balances in that
bucket, sums to a required allowance, and reports the movement
needed to get from the allowance already carried to the one now
required. The movement is the number that matters and the one
naive code gets wrong: the period's bad-debt expense is not the
whole required allowance, it is the increase over what was already
provided, and expensing the full allowance every period charges the
same losses again and again. A rate outside zero to one is refused,
since a bucket cannot lose more than it holds, and a required
allowance is never negative even when every rate is zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.aging import AgingReport
from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


@dataclass(frozen=True)
class ProvisionLine:
    bucket: str
    balance: int
    rate: Fraction
    provided: int


@dataclass(frozen=True)
class Provision:
    currency: str
    lines: tuple[ProvisionLine, ...]
    required: Money
    existing: Money

    def movement(self) -> Money:
        # The period's expense is the increase over what was already
        # provided, not the whole allowance charged again.
        return self.required - self.existing

    def is_release(self) -> bool:
        return self.movement().is_negative()


def provision_for(
    report: AgingReport,
    rates: dict[str, Fraction],
    existing: Money,
    mode: Rounding = Rounding.HALF_EVEN,
) -> Provision:
    for bucket, rate in rates.items():
        if rate < 0 or rate > 1:
            raise Refused(
                f"the loss rate for {bucket!r} is outside zero to one; a bucket "
                "cannot lose more than it holds"
            )
    existing.same_currency(report.total())
    lines: list[ProvisionLine] = []
    required = 0
    for bucket, balance in report.buckets:
        rate = rates.get(bucket, Fraction(0))
        provided = round_money(
            Fraction(balance) * rate, report.currency, mode
        ).units
        required += provided
        lines.append(ProvisionLine(bucket, balance, rate, provided))
    return Provision(
        currency=report.currency,
        lines=tuple(lines),
        required=Money.from_minor(required, report.currency),
        existing=existing,
    )
