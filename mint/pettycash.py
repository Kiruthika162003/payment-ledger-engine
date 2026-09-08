"""Petty cash on the imprest system: the float is fixed, so the tin must always add up.

Petty cash is run on an old and clever control called imprest: the
tin is set to a fixed float, say two hundred, and every payment out
leaves a voucher behind, so at any moment the cash plus the
vouchers must equal the float exactly. That single equation is the
control. A shortage shows up immediately as cash plus vouchers
falling short, without anyone needing to remember what the balance
should have been, and topping the tin back up to the float is done
by reimbursing precisely the vouchers, which makes the top-up
self-checking too. This module implements that equation and reports
the variance rather than hiding it, because a tin that is a few
dollars short is a fact somebody needs to know and a system that
silently adjusts the float to match the count has destroyed the
only control petty cash has. Increasing or decreasing the float is
a deliberate act with its own record, so a change to the float can
never be confused with a shortage.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class Voucher:
    id: str
    date: datetime.date
    amount: Money
    purpose: str
    approved_by: str


@dataclass
class PettyCash:
    float_amount: Money
    cash_on_hand: Money
    vouchers: list[Voucher] = field(default_factory=list)
    float_changes: list[tuple[datetime.date, Money, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cash_on_hand.same_currency(self.float_amount)
        if not self.float_amount.is_positive():
            raise Refused("a petty cash float is a positive amount")

    def voucher_total(self) -> Money:
        total = Money.zero(self.float_amount.currency)
        for voucher in self.vouchers:
            total = total + voucher.amount
        return total

    def accounted_for(self) -> Money:
        return self.cash_on_hand + self.voucher_total()

    def variance(self) -> Money:
        # The whole control in one line: cash plus vouchers against the float.
        return self.accounted_for() - self.float_amount

    def is_balanced(self) -> bool:
        return self.variance().is_zero()

    def is_short(self) -> bool:
        return self.variance().is_negative()

    def spend(
        self,
        voucher_id: str,
        amount: Money,
        on: datetime.date,
        purpose: str,
        approved_by: str,
    ) -> Voucher:
        amount.same_currency(self.float_amount)
        if not amount.is_positive():
            raise Refused("a petty cash payment is a positive amount")
        if not purpose.strip():
            raise Refused("a voucher records what the money was for")
        if not approved_by.strip():
            raise Refused("a voucher names who approved it")
        if amount > self.cash_on_hand:
            raise Refused(
                f"a payment of {amount.format()} exceeds the "
                f"{self.cash_on_hand.format()} in the tin"
            )
        if any(existing.id == voucher_id for existing in self.vouchers):
            raise Refused(f"voucher {voucher_id!r} already exists")
        voucher = Voucher(voucher_id, on, amount, purpose.strip(), approved_by.strip())
        self.vouchers.append(voucher)
        self.cash_on_hand = self.cash_on_hand - amount
        return voucher

    def reimbursement_due(self) -> Money:
        return self.voucher_total()

    def reimburse(self) -> Money:
        # Reimbursing exactly the vouchers restores the float, which is what
        # makes the top-up self-checking.
        if not self.vouchers:
            raise Refused("there are no vouchers to reimburse")
        amount = self.reimbursement_due()
        self.cash_on_hand = self.cash_on_hand + amount
        self.vouchers.clear()
        return amount

    def count_cash(self, counted: Money) -> Money:
        counted.same_currency(self.float_amount)
        if counted.is_negative():
            raise Refused("a cash count is not negative")
        self.cash_on_hand = counted
        return self.variance()

    def change_float(self, new_float: Money, on: datetime.date, reason: str) -> Money:
        new_float.same_currency(self.float_amount)
        if not new_float.is_positive():
            raise Refused("a float stays positive")
        if not reason.strip():
            raise Refused(
                "changing the float is a deliberate act with a reason, so it "
                "can never be confused with a shortage"
            )
        difference = new_float - self.float_amount
        self.float_changes.append((on, difference, reason.strip()))
        self.float_amount = new_float
        self.cash_on_hand = self.cash_on_hand + difference
        return self.float_amount
