"""Postings: one line of an entry, a positive amount on a named side.

A posting is the atom of a ledger: an amount of money placed on
one account, on either the debit or the credit side. This module
keeps the amount positive and names the side explicitly rather
than encoding direction as a sign, because a signed amount forces
every reader to remember whether positive means debit for this
account type or the opposite, while an explicit side reads the way
an accountant speaks, debit cash, credit revenue. A posting of
zero is refused, since a line that moves nothing is either a
mistake or noise that will later be mistaken for a real movement,
and a negative amount is refused with the remedy named, flip the
side instead, because a negative debit is a credit wearing a
disguise and the disguise is exactly what makes fraud and error
hard to see. The convenience constructors debit and credit are the
way the rest of the package builds postings, so the side is chosen
by the function name at the call site and cannot be gotten
backwards by passing the wrong enum.
"""

from __future__ import annotations

from dataclasses import dataclass

from mint.accounts import Side
from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class Posting:
    account: str
    amount: Money
    side: Side

    def __post_init__(self) -> None:
        if self.amount.is_negative():
            raise Refused(
                f"a posting of {self.amount.format()} is negative; flip the "
                "side to debit or credit instead of signing the amount"
            )
        if self.amount.is_zero():
            raise Refused(
                "a posting of zero moves nothing; a ledger does not record "
                "lines that will later be mistaken for real movements"
            )

    @property
    def currency(self) -> str:
        return self.amount.currency

    def debit_units(self) -> int:
        return self.amount.units if self.side is Side.DEBIT else 0

    def credit_units(self) -> int:
        return self.amount.units if self.side is Side.CREDIT else 0

    def is_debit(self) -> bool:
        return self.side is Side.DEBIT

    def signed_for(self, debit_normal: bool) -> int:
        # The amount as it moves an account of the given normality: a
        # debit grows a debit-normal account and shrinks the others.
        grows = self.is_debit() == debit_normal
        return self.amount.units if grows else -self.amount.units

    def flip(self) -> Posting:
        return Posting(self.account, self.amount, self.side.opposite())


def debit(account: str, amount: Money) -> Posting:
    return Posting(account, amount, Side.DEBIT)


def credit(account: str, amount: Money) -> Posting:
    return Posting(account, amount, Side.CREDIT)
