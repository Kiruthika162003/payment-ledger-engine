"""Franchising: the joining fee, the running royalty, and the fund that is not revenue.

A franchise agreement has three money flows and they are accounted
for differently, which is why franchisors get this wrong. The
initial fee buys the right to operate and is recognized as the
franchisor performs what it promised in return, usually training
and the site opening, rather than banked the day the contract is
signed; recognizing it on signature books revenue for work not yet
done. The ongoing royalty is a share of the franchisee's sales and
is earned as those sales happen, which makes it the easy one. The
advertising fund is the one that catches people: contributions are
collected for a specific purpose and held for it, so they are not
the franchisor's revenue at all but a liability spent on behalf of
the franchisees, and any surplus stays in the fund rather than
falling to profit. This module keeps the three apart and reports
the fund balance separately, since a franchisor that has spent the
fund on itself has taken money it was holding.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


@dataclass
class FranchiseAgreement:
    id: str
    franchisee: str
    initial_fee: Money
    royalty_rate: Fraction
    ad_fund_rate: Fraction
    signed_on: datetime.date
    obligations_total: int = 1
    obligations_met: int = 0
    initial_fee_recognized: Money | None = None
    reported_sales: Money | None = None
    royalties_earned: Money | None = None
    fund_collected: Money | None = None
    fund_spent: Money | None = None

    def __post_init__(self) -> None:
        for rate in (self.royalty_rate, self.ad_fund_rate):
            if rate < 0 or rate >= 1:
                raise Refused("a franchise rate is a fraction below one")
        if not self.initial_fee.is_positive():
            raise Refused("an initial franchise fee is positive")
        if self.obligations_total < 1:
            raise Refused("a franchise agreement has at least one obligation")
        currency = self.initial_fee.currency
        zero = Money.zero(currency)
        self.initial_fee_recognized = self.initial_fee_recognized or zero
        self.reported_sales = self.reported_sales or zero
        self.royalties_earned = self.royalties_earned or zero
        self.fund_collected = self.fund_collected or zero
        self.fund_spent = self.fund_spent or zero

    def currency(self) -> str:
        return self.initial_fee.currency

    def deferred_initial_fee(self) -> Money:
        return self.initial_fee - self.initial_fee_recognized

    def meet_obligation(self) -> Money:
        # Recognized as the promised work is done, not on signature.
        if self.obligations_met >= self.obligations_total:
            raise Refused(
                f"every obligation on agreement {self.id!r} is already met"
            )
        self.obligations_met += 1
        if self.obligations_met == self.obligations_total:
            recognized = self.deferred_initial_fee()
        else:
            share = Fraction(self.obligations_met, self.obligations_total)
            target = scale(self.initial_fee, share, Rounding.HALF_EVEN)
            recognized = target - self.initial_fee_recognized
        self.initial_fee_recognized = self.initial_fee_recognized + recognized
        return recognized

    def report_sales(self, amount: Money) -> tuple[Money, Money]:
        amount.same_currency(self.initial_fee)
        if not amount.is_positive():
            raise Refused("reported sales are a positive amount")
        self.reported_sales = self.reported_sales + amount
        royalty = scale(amount, self.royalty_rate, Rounding.HALF_EVEN)
        contribution = scale(amount, self.ad_fund_rate, Rounding.HALF_EVEN)
        self.royalties_earned = self.royalties_earned + royalty
        self.fund_collected = self.fund_collected + contribution
        return royalty, contribution

    def spend_fund(self, amount: Money, purpose: str) -> Money:
        amount.same_currency(self.initial_fee)
        if not purpose.strip():
            raise Refused("advertising fund spending records its purpose")
        if amount > self.fund_balance():
            raise Refused(
                f"spending {amount.format()} exceeds the "
                f"{self.fund_balance().format()} held in the advertising fund"
            )
        self.fund_spent = self.fund_spent + amount
        return self.fund_balance()

    def fund_balance(self) -> Money:
        # A liability, not revenue: collected for a purpose and held for it.
        return self.fund_collected - self.fund_spent

    def franchisor_revenue(self) -> Money:
        return self.initial_fee_recognized + self.royalties_earned

    def fund_is_revenue(self) -> bool:
        return False

    def is_fully_opened(self) -> bool:
        return self.obligations_met >= self.obligations_total


@dataclass
class FranchiseNetwork:
    currency: str
    agreements: list[FranchiseAgreement] = field(default_factory=list)

    def add(self, agreement: FranchiseAgreement) -> FranchiseAgreement:
        if agreement.currency() != self.currency:
            raise Refused(
                f"agreement {agreement.id!r} is in {agreement.currency()}, not "
                f"{self.currency}"
            )
        if any(existing.id == agreement.id for existing in self.agreements):
            raise Refused(f"agreement {agreement.id!r} is already in the network")
        self.agreements.append(agreement)
        return agreement

    def total_revenue(self) -> Money:
        total = Money.zero(self.currency)
        for agreement in self.agreements:
            total = total + agreement.franchisor_revenue()
        return total

    def total_fund_held(self) -> Money:
        total = Money.zero(self.currency)
        for agreement in self.agreements:
            total = total + agreement.fund_balance()
        return total

    def total_deferred(self) -> Money:
        total = Money.zero(self.currency)
        for agreement in self.agreements:
            total = total + agreement.deferred_initial_fee()
        return total
