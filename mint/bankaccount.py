"""Bank accounts: available versus ledger balance, and the holds between them.

The single most misunderstood thing about a bank account is that it
has two balances, not one. The ledger balance is what has settled;
the available balance is the ledger balance less the holds placed
against it and plus nothing at all, because a deposit that has not
cleared is not spendable however encouraging it looks. Systems that
track one number authorize spending against money that is already
committed, and the customer discovers this as an overdraft they did
not cause. This module keeps both balances and the holds that
separate them. A hold reserves an amount against the available
balance without moving the ledger balance, is released when the
transaction it guarded settles or expires, and cannot exceed what is
available when placed. Deposits carry an availability date, so
funds credited to the ledger today may become available tomorrow,
which is exactly the float that makes the two balances differ. An
overdraft limit can be granted explicitly, and spending into it is
allowed up to the limit and refused past it, so an overdraft is a
decision the bank made rather than a bug the customer found.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.errors import InsufficientFunds, Refused
from mint.money import Money


@dataclass(frozen=True)
class Deposit:
    date: datetime.date
    amount: Money
    available_on: datetime.date
    memo: str


@dataclass
class Hold:
    id: str
    amount: Money
    placed: datetime.date
    expires: datetime.date | None = None
    released: bool = False

    def is_active(self, as_of: datetime.date) -> bool:
        if self.released:
            return False
        return self.expires is None or as_of <= self.expires


@dataclass
class BankAccount:
    id: str
    currency: str
    overdraft_limit: Money | None = None
    deposits: list[Deposit] = field(default_factory=list)
    withdrawals: list[tuple[datetime.date, Money, str]] = field(default_factory=list)
    holds: list[Hold] = field(default_factory=list)

    def ledger_balance(self, as_of: datetime.date) -> Money:
        total = Money.zero(self.currency)
        for deposit in self.deposits:
            if deposit.date <= as_of:
                total = total + deposit.amount
        for date, amount, _memo in self.withdrawals:
            if date <= as_of:
                total = total - amount
        return total

    def cleared_balance(self, as_of: datetime.date) -> Money:
        total = Money.zero(self.currency)
        for deposit in self.deposits:
            if deposit.available_on <= as_of:
                total = total + deposit.amount
        for date, amount, _memo in self.withdrawals:
            if date <= as_of:
                total = total - amount
        return total

    def held_total(self, as_of: datetime.date) -> Money:
        total = Money.zero(self.currency)
        for hold in self.holds:
            if hold.is_active(as_of):
                total = total + hold.amount
        return total

    def available_balance(self, as_of: datetime.date) -> Money:
        return self.cleared_balance(as_of) - self.held_total(as_of)

    def spending_power(self, as_of: datetime.date) -> Money:
        available = self.available_balance(as_of)
        if self.overdraft_limit is None:
            return available
        return available + self.overdraft_limit

    def deposit(
        self,
        amount: Money,
        on: datetime.date,
        available_on: datetime.date | None = None,
        memo: str = "deposit",
    ) -> Money:
        self._guard(amount)
        cleared = available_on or on
        if cleared < on:
            raise Refused("funds cannot become available before they are deposited")
        self.deposits.append(Deposit(on, amount, cleared, memo))
        return self.ledger_balance(on)

    def withdraw(self, amount: Money, on: datetime.date, memo: str = "withdrawal") -> Money:
        self._guard(amount)
        if amount > self.spending_power(on):
            raise InsufficientFunds(
                f"a withdrawal of {amount.format()} exceeds the "
                f"{self.spending_power(on).format()} spendable in account "
                f"{self.id!r}; uncleared deposits and holds are not spendable"
            )
        self.withdrawals.append((on, amount, memo))
        return self.available_balance(on)

    def place_hold(
        self,
        hold_id: str,
        amount: Money,
        on: datetime.date,
        expires: datetime.date | None = None,
    ) -> Hold:
        self._guard(amount)
        if amount > self.available_balance(on):
            raise InsufficientFunds(
                f"a hold of {amount.format()} exceeds the "
                f"{self.available_balance(on).format()} available"
            )
        hold = Hold(hold_id, amount, on, expires)
        self.holds.append(hold)
        return hold

    def release_hold(self, hold_id: str) -> Hold:
        for hold in self.holds:
            if hold.id == hold_id:
                if hold.released:
                    raise Refused(f"hold {hold_id!r} is already released")
                hold.released = True
                return hold
        raise Refused(f"there is no hold {hold_id!r} on account {self.id!r}")

    def is_overdrawn(self, as_of: datetime.date) -> bool:
        return self.ledger_balance(as_of).is_negative()

    def _guard(self, amount: Money) -> None:
        if amount.currency != self.currency:
            raise Refused(
                f"account {self.id!r} holds {self.currency}, not {amount.currency}"
            )
        if not amount.is_positive():
            raise Refused("a bank movement carries a positive amount")
