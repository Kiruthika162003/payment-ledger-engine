"""Share capital: par value, the premium above it, and what may lawfully be paid out.

Shares issued for more than their nominal value split into two
different things, and the split matters because they are not
equally available. The nominal amount goes to share capital, which
is locked in as the creditors' buffer and cannot be distributed;
the excess goes to a share premium account, which in most
jurisdictions is equally undistributable. Only retained earnings
are distributable, which is why a company with enormous share
capital can still be unable to pay a dividend. This module keeps
the three apart and computes the distributable figure from them, so
the dividend check has a number to test against rather than an
intuition. Buying back shares reduces capital and is paid out of
distributable reserves, which is the rule that stops a company
returning capital to some shareholders at the expense of creditors,
and the module refuses a buyback that would breach it. Issuing
below par is refused outright, since it would create capital that
was never contributed.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class Issue:
    date: datetime.date
    shares: int
    price_per_share: Money
    par_value: Money

    def __post_init__(self) -> None:
        self.par_value.same_currency(self.price_per_share)
        if self.shares < 1:
            raise Refused("an issue creates at least one share")
        if self.price_per_share < self.par_value:
            raise Refused(
                "shares cannot be issued below par; doing so would create "
                "capital that was never contributed"
            )

    def nominal_total(self) -> Money:
        return Money.from_minor(
            self.par_value.units * self.shares, self.par_value.currency
        )

    def premium_total(self) -> Money:
        excess = self.price_per_share - self.par_value
        return Money.from_minor(excess.units * self.shares, excess.currency)

    def proceeds(self) -> Money:
        return self.nominal_total() + self.premium_total()


@dataclass
class ShareCapital:
    currency: str
    par_value: Money
    retained_earnings: Money | None = None
    issues: list[Issue] = field(default_factory=list)
    buybacks: list[tuple[datetime.date, int, Money]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.par_value.currency != self.currency:
            raise Refused(
                f"the par value is in {self.par_value.currency}, not {self.currency}"
            )
        if not self.par_value.is_positive():
            raise Refused("a par value is positive")
        if self.retained_earnings is None:
            self.retained_earnings = Money.zero(self.currency)

    def issue(
        self, shares: int, price_per_share: Money, on: datetime.date
    ) -> Issue:
        if price_per_share.currency != self.currency:
            raise Refused(
                f"an issue priced in {price_per_share.currency} does not belong "
                f"to a {self.currency} register"
            )
        item = Issue(on, shares, price_per_share, self.par_value)
        self.issues.append(item)
        return item

    def shares_issued(self) -> int:
        issued = sum(item.shares for item in self.issues)
        bought = sum(shares for _, shares, _ in self.buybacks)
        return issued - bought

    def share_capital(self) -> Money:
        return Money.from_minor(
            self.par_value.units * self.shares_issued(), self.currency
        )

    def share_premium(self) -> Money:
        total = Money.zero(self.currency)
        for item in self.issues:
            total = total + item.premium_total()
        return total

    def total_equity(self) -> Money:
        return self.share_capital() + self.share_premium() + self.retained_earnings

    def distributable_reserves(self) -> Money:
        # Only retained earnings: capital and premium are the creditors'
        # buffer, which is why a company with huge capital may still be
        # unable to pay a dividend.
        return (
            self.retained_earnings
            if self.retained_earnings.is_positive()
            else Money.zero(self.currency)
        )

    def can_distribute(self, amount: Money) -> bool:
        amount.same_currency(self.par_value)
        return amount <= self.distributable_reserves()

    def earn(self, profit: Money) -> Money:
        profit.same_currency(self.par_value)
        self.retained_earnings = self.retained_earnings + profit
        return self.retained_earnings

    def buy_back(
        self, shares: int, price_per_share: Money, on: datetime.date
    ) -> Money:
        price_per_share.same_currency(self.par_value)
        if shares < 1:
            raise Refused("a buyback repurchases at least one share")
        if shares > self.shares_issued():
            raise Refused(
                f"a buyback of {shares} shares exceeds the "
                f"{self.shares_issued()} in issue"
            )
        cost = Money.from_minor(price_per_share.units * shares, self.currency)
        if not self.can_distribute(cost):
            raise Refused(
                f"a buyback costing {cost.format()} exceeds the "
                f"{self.distributable_reserves().format()} distributable; "
                "returning capital ahead of creditors is what the rule prevents"
            )
        self.buybacks.append((on, shares, price_per_share))
        self.retained_earnings = self.retained_earnings - cost
        return cost

    def total_raised(self) -> Money:
        total = Money.zero(self.currency)
        for item in self.issues:
            total = total + item.proceeds()
        return total
