"""Affordability: can they pay it now, and can they still pay it if rates rise.

Lending responsibly means asking two questions, and lenders that
skipped the second one caused a financial crisis. The first is
whether the borrower can service the debt today: the payment plus
existing commitments against income, the debt-to-income ratio. The
second is whether they could still service it if circumstances
worsened, which is the stress test: recompute the payment at a rate
several points higher and ask the same question again. A loan that
passes the first and fails the second is affordable only until the
weather changes, and this module reports both verdicts separately
rather than collapsing them, because a lender that only sees the
combined answer cannot tell a comfortable borrower from a fragile
one. Disposable income is checked as well as the ratio, since a
ratio is proportional and a low-income household passing on
percentage can still be left with too little to live on, which is
the failure a pure ratio test cannot see.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.amortization import schedule
from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class AffordabilityPolicy:
    max_debt_to_income: Fraction
    stress_uplift: Fraction
    minimum_disposable: Money

    def __post_init__(self) -> None:
        if self.max_debt_to_income <= 0 or self.max_debt_to_income >= 1:
            raise Refused("a debt-to-income limit is a fraction below one")
        if self.stress_uplift < 0:
            raise Refused("a stress uplift is not negative")
        if self.minimum_disposable.is_negative():
            raise Refused("a disposable income floor is not negative")


@dataclass(frozen=True)
class Assessment:
    monthly_payment: Money
    stressed_payment: Money
    debt_to_income: Fraction
    stressed_debt_to_income: Fraction
    disposable: Money
    stressed_disposable: Money
    passes_today: bool
    passes_stressed: bool

    def verdict(self) -> str:
        if self.passes_today and self.passes_stressed:
            return "affordable"
        if self.passes_today:
            return "affordable only until the weather changes"
        return "not affordable"

    def is_fragile(self) -> bool:
        return self.passes_today and not self.passes_stressed


def monthly_payment_for(
    principal: Money, annual_rate: Fraction, months: int
) -> Money:
    return schedule(principal, annual_rate, months, 12).level_payment


def assess(
    principal: Money,
    annual_rate: Fraction,
    months: int,
    monthly_income: Money,
    existing_commitments: Money,
    essential_costs: Money,
    policy: AffordabilityPolicy,
) -> Assessment:
    for value in (monthly_income, existing_commitments, essential_costs):
        value.same_currency(principal)
    if not monthly_income.is_positive():
        raise Refused("an affordability assessment needs positive income")

    payment = monthly_payment_for(principal, annual_rate, months)
    stressed = monthly_payment_for(principal, annual_rate + policy.stress_uplift, months)

    total_now = payment + existing_commitments
    total_stressed = stressed + existing_commitments
    ratio = Fraction(total_now.units, monthly_income.units)
    stressed_ratio = Fraction(total_stressed.units, monthly_income.units)

    disposable = monthly_income - total_now - essential_costs
    stressed_disposable = monthly_income - total_stressed - essential_costs

    return Assessment(
        monthly_payment=payment,
        stressed_payment=stressed,
        debt_to_income=ratio,
        stressed_debt_to_income=stressed_ratio,
        disposable=disposable,
        stressed_disposable=stressed_disposable,
        passes_today=(
            ratio <= policy.max_debt_to_income
            and disposable >= policy.minimum_disposable
        ),
        passes_stressed=(
            stressed_ratio <= policy.max_debt_to_income
            and stressed_disposable >= policy.minimum_disposable
        ),
    )


def maximum_advance(
    annual_rate: Fraction,
    months: int,
    monthly_income: Money,
    existing_commitments: Money,
    essential_costs: Money,
    policy: AffordabilityPolicy,
    step: int = 100,
) -> Money:
    # Walked upward rather than solved, because the payment formula is
    # rounded and the largest affordable advance is whatever actually passes.
    currency = monthly_income.currency
    best = Money.zero(currency)
    candidate = Money.from_minor(step * 100, currency)
    for _ in range(2000):
        result = assess(
            candidate,
            annual_rate,
            months,
            monthly_income,
            existing_commitments,
            essential_costs,
            policy,
        )
        if not (result.passes_today and result.passes_stressed):
            break
        best = candidate
        candidate = candidate + Money.from_minor(step * 100, currency)
    return best
