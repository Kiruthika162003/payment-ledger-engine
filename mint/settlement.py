"""Settlement: netting a day's charges, refunds, and fees into one payout.

A processor does not wire money for every card swipe; it batches a
period's activity and pays the net once, and the ledger has to
model that batch or it will book gross receipts that never arrived
in the bank. A settlement takes the charges captured, the refunds
issued, and the fees charged for the period, all in one currency,
and reduces them to a single payout: charges less refunds less
fees. The one-currency rule is strict, because a payout is a wire
in a specific currency and summing dollars with euros produces a
figure no bank will honor; a batch handed mixed currencies is
refused rather than converted at a rate no one chose. The batch
reports its parts, gross charges, gross refunds, and fees, beside
the net, so the payout can be tied back to what produced it, which
is exactly the tie-out a finance team performs when the bank
credit lands and they ask what it was for. A net that comes out
negative is allowed and reported as such, since a day of heavy
refunds genuinely owes the processor money, and hiding that behind
a floor of zero would misstate the balance owed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mint.errors import CurrencyMismatch, Refused
from mint.money import Money


class ItemKind(Enum):
    CHARGE = "charge"
    REFUND = "refund"
    FEE = "fee"


@dataclass(frozen=True)
class SettlementItem:
    kind: ItemKind
    amount: Money


@dataclass(frozen=True)
class SettlementBatch:
    currency: str
    gross_charges: Money
    gross_refunds: Money
    fees: Money
    net: Money
    item_count: int

    def owes_processor(self) -> bool:
        return self.net.is_negative()


def settle(items: list[SettlementItem], currency: str) -> SettlementBatch:
    currency = currency.upper()
    if not items:
        raise Refused("a settlement batch needs at least one item")
    charges = Money.zero(currency)
    refunds = Money.zero(currency)
    fees = Money.zero(currency)
    for item in items:
        if item.amount.currency != currency:
            raise CurrencyMismatch(
                f"a settlement in {currency} cannot include a "
                f"{item.amount.currency} item; a payout is one currency"
            )
        if not item.amount.is_positive():
            raise Refused("every settlement item carries a positive amount")
        if item.kind is ItemKind.CHARGE:
            charges = charges + item.amount
        elif item.kind is ItemKind.REFUND:
            refunds = refunds + item.amount
        else:
            fees = fees + item.amount
    net = charges - refunds - fees
    return SettlementBatch(
        currency=currency,
        gross_charges=charges,
        gross_refunds=refunds,
        fees=fees,
        net=net,
        item_count=len(items),
    )
