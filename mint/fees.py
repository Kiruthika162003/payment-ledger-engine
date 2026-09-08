"""Processing fees: a percentage plus a fixed piece, and the inverse that grosses up.

The standard payment fee is a percentage of the amount plus a
fixed piece, the familiar form of a card processor's price, and
this module computes it and the harder inverse. Forward is easy:
multiply, round, add the fixed piece, and the net the merchant
keeps is the charge less the fee. The inverse is the one people get
wrong. A merchant who wants to net a specific amount cannot simply
add the fee to it, because the fee is a percentage of the larger
grossed-up total, not of the net, so the correct gross solves net
equals gross minus gross times rate minus fixed, which rearranges
to gross equals net plus fixed over one minus rate. This module
provides that gross-up so a business can charge the customer the
amount that leaves it whole after fees, and it rounds the gross up
rather than to nearest, because rounding a gross-up down leaves the
merchant a cent short of the target every time. A fee that would
exceed the amount it is charged on is refused, since a charge that
nets negative is not a sale, it is a slow way to give money away.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money, scale


@dataclass(frozen=True)
class FeeBreakdown:
    gross: Money
    fee: Money
    net: Money

    def reconciles(self) -> bool:
        return self.net + self.fee == self.gross


@dataclass(frozen=True)
class FeeSchedule:
    percent: Fraction
    fixed: Money

    def __post_init__(self) -> None:
        if self.percent < 0 or self.percent >= 1:
            raise Refused("a percentage fee is a fraction between zero and one")
        if self.fixed.is_negative():
            raise Refused("a fixed fee is not negative")

    def charge(self, amount: Money) -> FeeBreakdown:
        amount.same_currency(self.fixed)
        fee = scale(amount, self.percent, Rounding.HALF_EVEN) + self.fixed
        if fee > amount:
            raise Refused(
                f"the fee {fee.format()} exceeds the charge {amount.format()}; "
                "a charge that nets negative is not a sale"
            )
        return FeeBreakdown(gross=amount, fee=fee, net=amount - fee)

    def gross_for_net(self, net: Money) -> FeeBreakdown:
        net.same_currency(self.fixed)
        if not net.is_positive():
            raise Refused("the target net must be positive")
        numerator = Fraction((net + self.fixed).units)
        gross_units = numerator / (1 - self.percent)
        gross = round_money(gross_units, net.currency, Rounding.CEILING)
        return self.charge(gross)
