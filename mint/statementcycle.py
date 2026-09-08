"""Credit card cycles: the grace period, the minimum payment, and what interest costs.

A credit card statement hides two rules that decide whether
borrowing is free or expensive. The first is the grace period: pay
the statement balance in full by the due date and no interest is
charged on purchases at all, but pay a cent less and interest is
charged on the whole balance from the transaction dates, not on the
remainder. That cliff is the single most misunderstood term in
consumer credit and this module models it exactly rather than
charging interest proportionally, because proportional interest
would make the statement look reasonable and the real one does not.
The second is the minimum payment, usually the larger of a fixed
floor and a small percentage of the balance, plus any interest and
fees, which is calculated to keep a balance outstanding for years.
The module reports the minimum, the interest that follows from
paying only it, and the months to clear at that rate, so the cost
of the minimum is visible rather than implied.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money, scale


@dataclass(frozen=True)
class CardTerms:
    annual_rate: Fraction
    minimum_floor: Money
    minimum_rate: Fraction

    def __post_init__(self) -> None:
        if self.annual_rate < 0:
            raise Refused("a card rate is not negative")
        if self.minimum_rate <= 0 or self.minimum_rate >= 1:
            raise Refused("a minimum payment rate is a fraction below one")
        if self.minimum_floor.is_negative():
            raise Refused("a minimum payment floor is not negative")

    def monthly_rate(self) -> Fraction:
        return self.annual_rate / 12


@dataclass(frozen=True)
class Statement:
    opening: Money
    purchases: Money
    payments: Money
    terms: CardTerms

    def closing(self) -> Money:
        return self.opening + self.purchases - self.payments

    def paid_in_full(self) -> bool:
        # The grace period is a cliff, not a slope: a cent short loses it.
        return self.payments >= self.opening and self.opening.is_positive()

    def minimum_payment(self) -> Money:
        balance = self.closing()
        if not balance.is_positive():
            return Money.zero(balance.currency)
        percentage = scale(balance, self.terms.minimum_rate, Rounding.CEILING)
        floor = self.terms.minimum_floor
        candidate = percentage if percentage > floor else floor
        return candidate if candidate < balance else balance

    def interest_charged(self) -> Money:
        balance = self.closing()
        if not balance.is_positive():
            return Money.zero(balance.currency)
        if self.paid_in_full():
            return Money.zero(balance.currency)
        return round_money(
            balance.times(self.terms.monthly_rate()),
            balance.currency,
            Rounding.HALF_EVEN,
        )

    def total_due(self) -> Money:
        return self.closing() + self.interest_charged()


def months_to_clear(balance: Money, terms: CardTerms, cap: int = 600) -> int | None:
    if not balance.is_positive():
        return 0
    running = balance
    monthly = terms.monthly_rate()
    for month in range(1, cap + 1):
        interest = round_money(running.times(monthly), running.currency)
        statement = Statement(
            opening=running,
            purchases=Money.zero(running.currency),
            payments=Money.zero(running.currency),
            terms=terms,
        )
        payment = statement.minimum_payment()
        if payment <= interest:
            # The minimum never covers the interest, so the balance grows.
            return None
        running = running + interest - payment
        if not running.is_positive():
            return month
    return None


def cost_of_minimum_only(balance: Money, terms: CardTerms, cap: int = 600) -> Money | None:
    months = months_to_clear(balance, terms, cap)
    if months is None:
        return None
    running = balance
    paid = Money.zero(balance.currency)
    monthly = terms.monthly_rate()
    for _ in range(months):
        interest = round_money(running.times(monthly), running.currency)
        statement = Statement(
            opening=running,
            purchases=Money.zero(running.currency),
            payments=Money.zero(running.currency),
            terms=terms,
        )
        payment = statement.minimum_payment()
        payment = payment if payment < running + interest else running + interest
        paid = paid + payment
        running = running + interest - payment
    return paid - balance
