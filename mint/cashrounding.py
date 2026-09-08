"""Cash rounding: paying in coins that do not exist, and booking the difference.

Several countries have withdrawn their smallest coins while keeping
the smaller unit for electronic payment, so a bill of 10.02 is paid
in cash as 10.00 while a card charge stays 10.02. The rounding is a
property of the tender, not of the price, and a system that rounds
the price instead misstates the invoice and the tax on it. This
module rounds only the cash tender, to the increment the currency
actually circulates, and reports the difference separately so the
ledger can book it as a rounding gain or loss, which is a real if
tiny income statement line and one that must exist for the books to
balance when the customer hands over less than the invoice says.
The rounding is to nearest with halves going up by default, the
convention most such schemes use, and the increment comes from the
currency registry rather than a constant, so the Swiss five-centime
and a five-cent scheme elsewhere both work without special cases. A
currency whose increment is a single minor unit rounds to itself
and reports a zero difference, which keeps callers from needing to
ask whether this currency rounds at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint import currency as currency_module
from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_fraction


@dataclass(frozen=True)
class CashTender:
    invoiced: Money
    tendered: Money
    difference: Money

    def rounds_down(self) -> bool:
        return self.difference.is_negative()

    def rounds_up(self) -> bool:
        return self.difference.is_positive()

    def is_exact(self) -> bool:
        return self.difference.is_zero()


def round_to_increment(
    amount: Money, increment: int, mode: Rounding = Rounding.HALF_UP
) -> Money:
    if increment < 1:
        raise Refused("a cash increment is at least one minor unit")
    steps = round_fraction(Fraction(amount.units, increment), mode)
    return Money.from_minor(steps * increment, amount.currency)


def tender(amount: Money, mode: Rounding = Rounding.HALF_UP) -> CashTender:
    spec = currency_module.get(amount.currency)
    rounded = round_to_increment(amount, spec.cash_increment, mode)
    return CashTender(
        invoiced=amount,
        tendered=rounded,
        difference=rounded - amount,
    )


def rounding_adjustment(amounts: list[Money], currency: str) -> Money:
    # The total gain or loss a till accumulates over a session; small per
    # sale and worth booking rather than losing.
    total = Money.zero(currency)
    for amount in amounts:
        if amount.currency != currency:
            raise Refused(
                f"a till session in {currency} cannot include a "
                f"{amount.currency} sale"
            )
        total = total + tender(amount).difference
    return total
