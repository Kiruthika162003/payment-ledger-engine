"""The bank reconciliation statement: two balances walked toward each other.

The bank's balance and the book's balance disagree almost always,
and almost always for good reasons: a cheque written but not yet
presented, a deposit made after the bank's cut-off, a fee the bank
charged that the books have not seen. The reconciliation statement
is the formal walk that turns each balance into the same adjusted
figure, and the discipline is that it walks from both ends rather
than adjusting one to match the other. Adjusting the books to the
bank would bury a real error; the point of walking both is that if
the two adjusted figures still differ, something is genuinely
wrong and the difference is exactly the size of the problem. So
this module computes both sides and reports the residual rather
than forcing it to zero. Items belong on one side or the other by
their nature: things the bank does not know about adjust the bank
side, things the books do not know about adjust the book side, and
putting an item on the wrong side moves the difference by twice its
value, which is the classic sign of a misplaced adjustment.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class RecItem:
    description: str
    amount: Money


@dataclass
class BankReconciliation:
    currency: str
    bank_balance: Money
    book_balance: Money
    deposits_in_transit: list[RecItem] = field(default_factory=list)
    outstanding_cheques: list[RecItem] = field(default_factory=list)
    bank_charges: list[RecItem] = field(default_factory=list)
    bank_credits: list[RecItem] = field(default_factory=list)
    book_errors: list[RecItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.book_balance.same_currency(self.bank_balance)

    def _guard(self, item: RecItem) -> RecItem:
        if item.amount.currency != self.currency:
            raise Refused(
                f"item {item.description!r} is in {item.amount.currency}, not "
                f"the reconciliation currency {self.currency}"
            )
        if not item.amount.is_positive():
            raise Refused(
                f"item {item.description!r} carries a positive amount; its side "
                "decides the direction, not its sign"
            )
        return item

    def add_deposit_in_transit(self, description: str, amount: Money) -> RecItem:
        item = self._guard(RecItem(description, amount))
        self.deposits_in_transit.append(item)
        return item

    def add_outstanding_cheque(self, description: str, amount: Money) -> RecItem:
        item = self._guard(RecItem(description, amount))
        self.outstanding_cheques.append(item)
        return item

    def add_bank_charge(self, description: str, amount: Money) -> RecItem:
        item = self._guard(RecItem(description, amount))
        self.bank_charges.append(item)
        return item

    def add_bank_credit(self, description: str, amount: Money) -> RecItem:
        item = self._guard(RecItem(description, amount))
        self.bank_credits.append(item)
        return item

    def add_book_error(self, description: str, amount: Money) -> RecItem:
        item = self._guard(RecItem(description, amount))
        self.book_errors.append(item)
        return item

    def _sum(self, items: list[RecItem]) -> Money:
        total = Money.zero(self.currency)
        for item in items:
            total = total + item.amount
        return total

    def adjusted_bank(self) -> Money:
        # Things the bank has not seen yet.
        return (
            self.bank_balance
            + self._sum(self.deposits_in_transit)
            - self._sum(self.outstanding_cheques)
        )

    def adjusted_book(self) -> Money:
        # Things the books have not seen yet.
        return (
            self.book_balance
            + self._sum(self.bank_credits)
            - self._sum(self.bank_charges)
            + self._sum(self.book_errors)
        )

    def difference(self) -> Money:
        return self.adjusted_bank() - self.adjusted_book()

    def reconciles(self) -> bool:
        return self.difference().is_zero()

    def summary(self) -> dict[str, Money]:
        return {
            "bank balance": self.bank_balance,
            "deposits in transit": self._sum(self.deposits_in_transit),
            "outstanding cheques": self._sum(self.outstanding_cheques),
            "adjusted bank": self.adjusted_bank(),
            "book balance": self.book_balance,
            "bank credits": self._sum(self.bank_credits),
            "bank charges": self._sum(self.bank_charges),
            "adjusted book": self.adjusted_book(),
            "difference": self.difference(),
        }
