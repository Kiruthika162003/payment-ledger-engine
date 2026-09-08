"""Accounts: the five types, and which side of the entry makes each one grow.

Double-entry bookkeeping rests on a convention that looks
arbitrary until it is not: every account is one of five types, and
each type has a natural side on which it increases. Assets and
expenses grow on the debit side; liabilities, equity, and income
grow on the credit side. The convention is not arbitrary at all,
it is the accounting equation rearranged, assets equal liabilities
plus equity, with income and expense as the temporary accounts
that feed equity, and the debit-and-credit rule is exactly what
keeps that equation in balance after every entry. This module
encodes the rule once, in one place, so the rest of the ledger
never has to remember which way a particular account moves: it
asks the account for its normal side and computes a signed balance
that is positive when the account holds what its type expects and
negative when it is contrary, an asset account gone negative being
an overdraft and a revenue account gone negative being a refund
that outran the sale. Keeping the sign convention in the type
rather than scattered through the posting code is what lets a
balance sheet and an income statement fall out of the same ledger
without a tangle of special cases.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AccountType(Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


class Side(Enum):
    DEBIT = "debit"
    CREDIT = "credit"

    def opposite(self) -> Side:
        return Side.CREDIT if self is Side.DEBIT else Side.DEBIT


_DEBIT_NORMAL = frozenset({AccountType.ASSET, AccountType.EXPENSE})


@dataclass(frozen=True)
class Account:
    code: str
    name: str
    type: AccountType
    currency: str
    parent: str | None = None

    def normal_side(self) -> Side:
        return Side.DEBIT if self.type in _DEBIT_NORMAL else Side.CREDIT

    def is_debit_normal(self) -> bool:
        return self.type in _DEBIT_NORMAL

    def signed_units(self, debit_units: int, credit_units: int) -> int:
        if self.is_debit_normal():
            return debit_units - credit_units
        return credit_units - debit_units

    def is_temporary(self) -> bool:
        # Income and expense accounts close into equity at period end.
        return self.type in (AccountType.INCOME, AccountType.EXPENSE)


def increases(account_type: AccountType) -> Side:
    return Side.DEBIT if account_type in _DEBIT_NORMAL else Side.CREDIT


def decreases(account_type: AccountType) -> Side:
    return increases(account_type).opposite()
