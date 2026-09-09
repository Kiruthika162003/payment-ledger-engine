"""Endowments: spend the return, never the capital, and know when you are underwater.

An endowment is a gift whose capital must be preserved in
perpetuity while its income supports the charity. The discipline
that makes it work is a spending policy: rather than spending
whatever the portfolio happened to earn this year, which would swing
the charity's budget with the market, the policy spends a fixed
percentage of a multi-year average value, so a good year and a bad
one are both smoothed. This module implements that. The condition
worth naming is being underwater, when the portfolio has fallen
below the original gift, because spending from an underwater
endowment is spending capital rather than return, and although some
jurisdictions permit it within limits, doing so unknowingly is how
a permanent fund is quietly consumed. So the module reports the
condition, computes the spend the policy allows, and refuses a
withdrawal that would take the fund below the corpus unless the
caller says explicitly that it may.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


@dataclass
class Endowment:
    id: str
    corpus: Money
    market_value: Money
    spending_rate: Fraction
    averaging_years: int = 3
    history: list[Money] = field(default_factory=list)
    distributed: Money | None = None

    def __post_init__(self) -> None:
        self.market_value.same_currency(self.corpus)
        if not self.corpus.is_positive():
            raise Refused("an endowment has a positive corpus")
        if self.spending_rate <= 0 or self.spending_rate >= 1:
            raise Refused("a spending rate is a fraction above zero and below one")
        if self.averaging_years < 1:
            raise Refused("a spending policy averages at least one year")
        if not self.history:
            self.history = [self.market_value]
        if self.distributed is None:
            self.distributed = Money.zero(self.corpus.currency)

    def record_value(self, value: Money) -> Money:
        value.same_currency(self.corpus)
        if value.is_negative():
            raise Refused("a market value is not negative")
        self.history.append(value)
        self.market_value = value
        return self.market_value

    def averaging_window(self) -> list[Money]:
        return self.history[-self.averaging_years :]

    def average_value(self) -> Money:
        window = self.averaging_window()
        total = sum(value.units for value in window)
        return Money.from_minor(total // len(window), self.corpus.currency)

    def permitted_spend(self) -> Money:
        # On the smoothed average, so a good year and a bad one both feed a
        # budget the charity can actually plan around.
        return round_money(
            self.average_value().times(self.spending_rate),
            self.corpus.currency,
            Rounding.HALF_EVEN,
        )

    def is_underwater(self) -> bool:
        return self.market_value < self.corpus

    def shortfall(self) -> Money:
        gap = self.corpus - self.market_value
        return gap if gap.is_positive() else Money.zero(self.corpus.currency)

    def headroom(self) -> Money:
        room = self.market_value - self.corpus
        return room if room.is_positive() else Money.zero(self.corpus.currency)

    def distribute(self, amount: Money, allow_invasion: bool = False) -> Money:
        amount.same_currency(self.corpus)
        if not amount.is_positive():
            raise Refused("a distribution is a positive amount")
        if amount > self.permitted_spend():
            raise Refused(
                f"a distribution of {amount.format()} exceeds the "
                f"{self.permitted_spend().format()} the spending policy allows"
            )
        if amount > self.market_value:
            raise Refused("an endowment cannot distribute more than it holds")
        would_leave = self.market_value - amount
        if would_leave < self.corpus and not allow_invasion:
            raise Refused(
                f"spending {amount.format()} would take endowment {self.id!r} "
                "below its corpus; that is spending capital, and doing it "
                "unknowingly is how a permanent fund is consumed"
            )
        self.market_value = would_leave
        self.history.append(self.market_value)
        self.distributed = self.distributed + amount
        return self.market_value

    def total_return(self) -> Money:
        return self.market_value + self.distributed - self.corpus

    def preserves_capital(self) -> bool:
        return not self.is_underwater()
