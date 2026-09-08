"""Sales tax: adding it on, backing it out, and stacking one tax on another.

Sales tax has three shapes a ledger must get right. Adding tax to
a net amount is the easy one, a multiply and a round. Backing tax
out of a tax-inclusive total is the one people botch, because the
tax is a fraction of the net and not of the total, so the net is
the total divided by one plus the rate, and multiplying the total
by the rate overstates the tax every time. The third shape is
compound tax, where a second tax applies to the amount already
grown by the first, as some provinces levy one tax on a base that
includes another; a system that always applies every rate to the
bare net understates a compound tax and remits too little. This
module does all three and keeps them reconciling: the net plus the
summed taxes equals the gross to the cent, which is the figure a
return demands and the confidence that it adds up. Rates are
fractions so the arithmetic is exact, and a negative rate is
refused, since a negative sales tax is a subsidy the form was not
built to carry.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money, scale


@dataclass(frozen=True)
class TaxLine:
    name: str
    rate: Fraction

    def __post_init__(self) -> None:
        if self.rate < 0:
            raise Refused(
                f"tax {self.name!r} has a negative rate; a negative sales tax "
                "is a subsidy the form was not built for"
            )


@dataclass(frozen=True)
class TaxBreakdown:
    net: Money
    taxes: tuple[tuple[str, int], ...]
    total_tax: Money
    gross: Money

    def reconciles(self) -> bool:
        return self.net + self.total_tax == self.gross


def apply_tax(
    net: Money,
    lines: list[TaxLine],
    compound: bool = False,
    mode: Rounding = Rounding.HALF_EVEN,
) -> TaxBreakdown:
    taxes: list[tuple[str, int]] = []
    base = net
    total = Money.zero(net.currency)
    for line in lines:
        piece = scale(base, line.rate, mode)
        taxes.append((line.name, piece.units))
        total = total + piece
        if compound:
            base = base + piece
    return TaxBreakdown(
        net=net,
        taxes=tuple(taxes),
        total_tax=total,
        gross=net + total,
    )


def extract_tax(gross: Money, rate: Fraction, name: str = "tax") -> TaxBreakdown:
    if rate < 0:
        raise Refused("a negative sales tax is a subsidy the form was not built for")
    net_units = round_money(
        Fraction(gross.units) / (1 + rate), gross.currency
    )
    tax = gross - net_units
    return TaxBreakdown(
        net=net_units,
        taxes=((name, tax.units),),
        total_tax=tax,
        gross=gross,
    )
