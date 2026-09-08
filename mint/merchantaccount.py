"""A merchant's account with a processor: what was earned, what is held, what is payable.

A merchant looking at their processor dashboard wants one thing:
how much money is coming and when. Getting there means separating
three balances that are easy to conflate. The gross is what
customers paid. The available balance is the gross less refunds,
fees, and chargebacks, which is what the merchant has actually
earned. The payable balance is the available less whatever is
still held in reserve or has not yet cleared the settlement delay,
which is what will actually arrive. A dashboard showing only the
first number produces a support ticket every payout day. This
module keeps the three apart and reports the movement between them
as named lines, so the difference between what was sold and what
lands in the bank can be read rather than guessed. Every movement
is recorded with its date, so the balance on any past day can be
reconstructed, which is what a merchant disputing a payout actually
needs.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.errors import InsufficientFunds, Refused
from mint.money import Money


class MovementKind(Enum):
    SALE = "sale"
    REFUND = "refund"
    FEE = "fee"
    CHARGEBACK = "chargeback"
    RESERVE_HELD = "reserve_held"
    RESERVE_RELEASED = "reserve_released"
    PAYOUT = "payout"


_REDUCES = frozenset(
    {
        MovementKind.REFUND,
        MovementKind.FEE,
        MovementKind.CHARGEBACK,
        MovementKind.PAYOUT,
    }
)


@dataclass(frozen=True)
class Movement:
    date: datetime.date
    kind: MovementKind
    amount: Money
    reference: str = ""

    def signed(self) -> Money:
        return -self.amount if self.kind in _REDUCES else self.amount


@dataclass
class MerchantAccount:
    merchant_id: str
    currency: str
    settlement_delay_days: int = 2
    movements: list[Movement] = field(default_factory=list)

    def _record(
        self, kind: MovementKind, amount: Money, on: datetime.date, reference: str
    ) -> Movement:
        if amount.currency != self.currency:
            raise Refused(
                f"account {self.merchant_id!r} settles in {self.currency}, not "
                f"{amount.currency}"
            )
        if not amount.is_positive():
            raise Refused("a movement carries a positive amount; its kind sets the sign")
        movement = Movement(on, kind, amount, reference)
        self.movements.append(movement)
        return movement

    def sale(self, amount: Money, on: datetime.date, reference: str = "") -> Movement:
        return self._record(MovementKind.SALE, amount, on, reference)

    def refund(self, amount: Money, on: datetime.date, reference: str = "") -> Movement:
        return self._record(MovementKind.REFUND, amount, on, reference)

    def fee(self, amount: Money, on: datetime.date, reference: str = "") -> Movement:
        return self._record(MovementKind.FEE, amount, on, reference)

    def chargeback(
        self, amount: Money, on: datetime.date, reference: str = ""
    ) -> Movement:
        return self._record(MovementKind.CHARGEBACK, amount, on, reference)

    def hold_reserve(self, amount: Money, on: datetime.date) -> Movement:
        return self._record(MovementKind.RESERVE_HELD, amount, on, "reserve")

    def release_reserve(self, amount: Money, on: datetime.date) -> Movement:
        return self._record(MovementKind.RESERVE_RELEASED, amount, on, "reserve")

    def gross_sales(self, as_of: datetime.date) -> Money:
        total = Money.zero(self.currency)
        for movement in self.movements:
            if movement.date <= as_of and movement.kind is MovementKind.SALE:
                total = total + movement.amount
        return total

    def _sum_of(self, kind: MovementKind, as_of: datetime.date) -> Money:
        total = Money.zero(self.currency)
        for movement in self.movements:
            if movement.date <= as_of and movement.kind is kind:
                total = total + movement.amount
        return total

    def available_balance(self, as_of: datetime.date) -> Money:
        # Reserve movements are excluded on both sides. A hold does not take
        # money out of available, it earmarks part of it, so crediting a
        # release back would add money the hold never removed.
        reserve_kinds = (MovementKind.RESERVE_HELD, MovementKind.RESERVE_RELEASED)
        total = Money.zero(self.currency)
        for movement in self.movements:
            if movement.date <= as_of and movement.kind not in reserve_kinds:
                total = total + movement.signed()
        return total

    def reserve_balance(self, as_of: datetime.date) -> Money:
        held = self._sum_of(MovementKind.RESERVE_HELD, as_of)
        released = self._sum_of(MovementKind.RESERVE_RELEASED, as_of)
        return held - released

    def uncleared(self, as_of: datetime.date) -> Money:
        # Sales inside the settlement delay have not cleared yet.
        cutoff = as_of - datetime.timedelta(days=self.settlement_delay_days)
        total = Money.zero(self.currency)
        for movement in self.movements:
            if movement.kind is MovementKind.SALE and movement.date > cutoff:
                total = total + movement.amount
        return total

    def payable_balance(self, as_of: datetime.date) -> Money:
        payable = (
            self.available_balance(as_of)
            - self.reserve_balance(as_of)
            - self.uncleared(as_of)
        )
        return payable if payable.is_positive() else Money.zero(self.currency)

    def pay_out(self, on: datetime.date) -> Money:
        amount = self.payable_balance(on)
        if not amount.is_positive():
            raise InsufficientFunds(
                f"account {self.merchant_id!r} has nothing payable on "
                f"{on.isoformat()}; reserves and uncleared sales are not payable"
            )
        self._record(MovementKind.PAYOUT, amount, on, "payout")
        return amount

    def statement(self, as_of: datetime.date) -> list[tuple[str, int]]:
        rows = [("gross sales", self.gross_sales(as_of).units)]
        for kind in (
            MovementKind.REFUND,
            MovementKind.FEE,
            MovementKind.CHARGEBACK,
            MovementKind.PAYOUT,
        ):
            rows.append((kind.value, -self._sum_of(kind, as_of).units))
        rows.append(("available", self.available_balance(as_of).units))
        rows.append(("held in reserve", self.reserve_balance(as_of).units))
        rows.append(("uncleared", self.uncleared(as_of).units))
        rows.append(("payable now", self.payable_balance(as_of).units))
        return rows
