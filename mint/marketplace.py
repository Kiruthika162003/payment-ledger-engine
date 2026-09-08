"""Marketplace splits: one buyer payment divided among sellers and the platform.

A marketplace collects one payment and owes several parties: the
sellers whose goods were bought, and itself for the commission. The
split has to be exact, because the platform's take is the residual
and any rounding error lands there silently, growing or shrinking
the platform's revenue by cents that nobody can explain. This
module computes the split with the cent conserved: seller amounts
are derived from their line values, the commission is taken from
each seller's share at the stated rate, and the platform's total is
whatever the sellers do not receive, so the parts always sum back
to the buyer's payment exactly. Because the commission is computed
per seller rather than once on the total, a marketplace with
different rates per seller works without special cases, which is
the common real requirement. Refunds run the split backward: a
refund of part of an order reduces the seller's share and claws
back the proportional commission, since a platform that keeps its
commission on refunded goods is charging for a sale that did not
happen.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


@dataclass(frozen=True)
class SellerLine:
    seller_id: str
    gross: Money
    commission_rate: Fraction

    def __post_init__(self) -> None:
        if not self.gross.is_positive():
            raise Refused(f"seller {self.seller_id!r} has no positive line value")
        if self.commission_rate < 0 or self.commission_rate >= 1:
            raise Refused(
                f"the commission rate for {self.seller_id!r} is not a fraction "
                "below one"
            )


@dataclass(frozen=True)
class SellerShare:
    seller_id: str
    gross: Money
    commission: Money
    net: Money


@dataclass(frozen=True)
class Split:
    payment: Money
    shares: tuple[SellerShare, ...]
    platform: Money

    def reconciles(self) -> bool:
        total = self.platform
        for share in self.shares:
            total = total + share.net
        return total == self.payment

    def seller(self, seller_id: str) -> SellerShare:
        for share in self.shares:
            if share.seller_id == seller_id:
                return share
        raise Refused(f"seller {seller_id!r} has no share in this split")


def split_payment(payment: Money, lines: list[SellerLine]) -> Split:
    if not lines:
        raise Refused("a marketplace split needs at least one seller line")
    gross_total = Money.zero(payment.currency)
    for line in lines:
        if line.gross.currency != payment.currency:
            raise Refused(
                f"seller {line.seller_id!r} is priced in {line.gross.currency}, "
                f"not the payment currency {payment.currency}"
            )
        gross_total = gross_total + line.gross
    if gross_total != payment:
        raise Refused(
            f"the seller lines total {gross_total.format()} but the payment is "
            f"{payment.format()}; a split must account for the whole payment"
        )
    shares: list[SellerShare] = []
    platform = Money.zero(payment.currency)
    for line in lines:
        commission = scale(line.gross, line.commission_rate, Rounding.HALF_EVEN)
        platform = platform + commission
        shares.append(
            SellerShare(
                seller_id=line.seller_id,
                gross=line.gross,
                commission=commission,
                net=line.gross - commission,
            )
        )
    return Split(payment=payment, shares=tuple(shares), platform=platform)


def split_refund(split: Split, seller_id: str, refund: Money) -> SellerShare:
    share = split.seller(seller_id)
    refund.same_currency(share.gross)
    if not refund.is_positive():
        raise Refused("a refund returns a positive amount")
    if refund > share.gross:
        raise Refused(
            f"a refund of {refund.format()} exceeds the {share.gross.format()} "
            f"sold by {seller_id!r}"
        )
    proportion = Fraction(refund.units, share.gross.units)
    clawback = scale(share.commission, proportion, Rounding.HALF_EVEN)
    return SellerShare(
        seller_id=seller_id,
        gross=refund,
        commission=clawback,
        net=refund - clawback,
    )
