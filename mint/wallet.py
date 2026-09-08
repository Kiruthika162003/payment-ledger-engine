"""Wallets: a stored-value balance that tops up, spends, and never goes red.

A wallet is prepaid money the customer has already handed over, so
the invariant that matters is that it cannot be spent past what was
loaded: a stored-value balance that goes negative has let a
customer spend money that is not there, which is a line of credit
nobody underwrote. This module keeps the balance as money in whole
minor units, tops it up by positive amounts, and refuses a spend
larger than the balance with a message naming the shortfall, so the
caller can prompt for a top-up rather than silently overdraw. Every
movement is recorded in order, because a wallet whose balance
cannot be explained by its own history is a wallet a customer will
dispute and the merchant cannot defend; the balance is the sum of
the movements, not a separate number that might drift from them. A
wallet holds one currency, chosen when it is opened, and a top-up
or spend in another currency is refused rather than converted at a
rate the customer never agreed to, since the whole appeal of a
wallet is that the money in it is exactly the money that was put
there.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.errors import InsufficientFunds, Refused
from mint.money import Money


@dataclass(frozen=True)
class WalletMovement:
    date: datetime.date
    amount: Money
    memo: str


@dataclass
class Wallet:
    id: str
    currency: str
    movements: list[WalletMovement] = field(default_factory=list)

    def balance(self) -> Money:
        total = Money.zero(self.currency)
        for movement in self.movements:
            total = total + movement.amount
        return total

    def _guard(self, amount: Money) -> None:
        if amount.currency != self.currency:
            raise Refused(
                f"wallet {self.id!r} holds {self.currency}; a "
                f"{amount.currency} movement would need a rate no one chose"
            )
        if not amount.is_positive():
            raise Refused("a wallet movement carries a positive amount")

    def top_up(self, amount: Money, on: datetime.date, memo: str = "top up") -> Money:
        self._guard(amount)
        self.movements.append(WalletMovement(on, amount, memo))
        return self.balance()

    def spend(self, amount: Money, on: datetime.date, memo: str = "spend") -> Money:
        self._guard(amount)
        if amount > self.balance():
            raise InsufficientFunds(
                f"a spend of {amount.format()} exceeds the "
                f"{self.balance().format()} in wallet {self.id!r}"
            )
        self.movements.append(WalletMovement(on, -amount, memo))
        return self.balance()

    def can_afford(self, amount: Money) -> bool:
        return amount.currency == self.currency and amount <= self.balance()
