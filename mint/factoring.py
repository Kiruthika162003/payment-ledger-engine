"""Factoring: selling receivables for cash now, and who eats it if they never pay.

A business short of cash can sell its invoices to a factor for less
than face value, taking money today instead of waiting for the
customer. The accounting turns entirely on one term: recourse. In a
non-recourse sale the factor bears the loss if the customer never
pays, so the receivable genuinely leaves the seller's balance sheet
and the discount is a loss recognized now. With recourse the seller
is still on the hook, so the transaction is a secured borrowing
wearing a sale's clothes, the receivable stays on the books and a
liability appears beside the cash. Treating a recourse sale as a
true sale removes an asset and a risk the business still carries,
which is exactly the window dressing the distinction exists to
prevent, so this module keeps the two apart and names which one it
is computing. The advance rate and the discount are separate terms:
the factor advances a fraction now and holds a reserve released
when the customer pays, less its fee, and the module reports each
piece so the seller can tie the cash they received to the invoice
they gave up.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


@dataclass(frozen=True)
class FactoringTerms:
    advance_rate: Fraction
    discount_rate: Fraction
    with_recourse: bool

    def __post_init__(self) -> None:
        if self.advance_rate <= 0 or self.advance_rate > 1:
            raise Refused("an advance rate is a fraction above zero and at most one")
        if self.discount_rate < 0 or self.discount_rate >= 1:
            raise Refused("a factoring discount is a fraction below one")


@dataclass(frozen=True)
class FactoringResult:
    face: Money
    advance: Money
    reserve: Money
    fee: Money
    with_recourse: bool

    def cash_today(self) -> Money:
        return self.advance

    def reserve_released(self) -> Money:
        return self.reserve - self.fee

    def total_received(self) -> Money:
        return self.advance + self.reserve_released()

    def cost(self) -> Money:
        return self.face - self.total_received()

    def stays_on_balance_sheet(self) -> bool:
        # With recourse the risk never left, so neither did the asset.
        return self.with_recourse

    def reconciles(self) -> bool:
        return self.total_received() + self.cost() == self.face


def factor(face: Money, terms: FactoringTerms) -> FactoringResult:
    if not face.is_positive():
        raise Refused("a factored receivable has a positive face value")
    advance = scale(face, terms.advance_rate, Rounding.HALF_EVEN)
    reserve = face - advance
    fee = scale(face, terms.discount_rate, Rounding.HALF_EVEN)
    if fee > reserve:
        raise Refused(
            f"the fee {fee.format()} exceeds the {reserve.format()} reserve; the "
            "seller would owe the factor money on a sale"
        )
    return FactoringResult(
        face=face,
        advance=advance,
        reserve=reserve,
        fee=fee,
        with_recourse=terms.with_recourse,
    )


def effective_annual_cost(
    result: FactoringResult, days_outstanding: int
) -> Fraction | None:
    if days_outstanding < 1 or result.advance.units == 0:
        return None
    period_cost = Fraction(result.cost().units, result.advance.units)
    return period_cost * Fraction(365, days_outstanding)
