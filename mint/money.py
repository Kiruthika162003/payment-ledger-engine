"""Money: a whole number of the smallest unit, never a float.

The mistake that corrupts more ledgers than any other is storing
money as a floating-point number, because a tenth of a dollar has
no exact binary representation and a few thousand additions of it
drift a ledger off its own books by a cent that no one can find.
This module stores money as an integer count of the currency's
smallest unit, cents for dollars and fils for dinars, so addition
and subtraction are exact by construction and the only place
rounding can enter is multiplication by a rate or a share, where
it is explicit and chosen. Money carries its currency with it and
refuses to add or compare across currencies, because a sum of
dollars and euros is not a smaller wrong number, it is a category
error, and the ledger names it as one. Construction from a human
amount goes through a decimal string, "10.50", parsed exactly
against the currency's exponent, and a float is refused at the
door with a message pointing at the string form, because the
moment a float becomes money the drift has already happened and no
downstream care can undo it. Equality across currencies is simply
false rather than an error, since asking whether ten dollars
equals ten euros is a fair question with a clear answer, but
ordering across currencies raises, since asking whether ten
dollars is less than ten euros is not a question the ledger can
answer without a rate it was not given.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint import currency as currency_module
from mint.errors import CurrencyMismatch, Refused


@dataclass(frozen=True)
class Money:
    units: int
    currency: str

    @classmethod
    def from_minor(cls, units: int, currency: str) -> Money:
        if not isinstance(units, int) or isinstance(units, bool):
            raise Refused(
                "minor units must be a whole number of the smallest unit; "
                "pass a decimal string to Money.of for a human amount"
            )
        currency_module.get(currency)
        return cls(units=units, currency=currency.upper())

    @classmethod
    def zero(cls, currency: str) -> Money:
        return cls.from_minor(0, currency)

    @classmethod
    def of(cls, amount: int | str, currency: str) -> Money:
        spec = currency_module.get(currency)
        if isinstance(amount, bool):
            raise Refused("a boolean is not an amount of money")
        if isinstance(amount, float):
            raise Refused(
                "a float cannot be money without losing cents; pass the "
                f"amount as a string such as '{amount:.2f}' instead"
            )
        if isinstance(amount, int):
            return cls.from_minor(amount * spec.minor_per_major(), currency)
        return cls.from_minor(_parse_decimal(amount, spec), currency)

    def same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatch(
                f"cannot combine {self.currency} and {other.currency}; "
                "convert one to the other through a posted rate first"
            )

    def __add__(self, other: Money) -> Money:
        self.same_currency(other)
        return Money(self.units + other.units, self.currency)

    def __sub__(self, other: Money) -> Money:
        self.same_currency(other)
        return Money(self.units - other.units, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.units, self.currency)

    def __abs__(self) -> Money:
        return Money(abs(self.units), self.currency)

    def times(self, factor: int | Fraction) -> Fraction:
        # Returns an exact fractional count of minor units; the caller
        # rounds through mint.rounding when it needs whole units back.
        return Fraction(self.units) * Fraction(factor)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.units == other.units and self.currency == other.currency

    def __hash__(self) -> int:
        return hash((self.units, self.currency))

    def __lt__(self, other: Money) -> bool:
        self.same_currency(other)
        return self.units < other.units

    def __le__(self, other: Money) -> bool:
        self.same_currency(other)
        return self.units <= other.units

    def __gt__(self, other: Money) -> bool:
        self.same_currency(other)
        return self.units > other.units

    def __ge__(self, other: Money) -> bool:
        self.same_currency(other)
        return self.units >= other.units

    def is_zero(self) -> bool:
        return self.units == 0

    def is_negative(self) -> bool:
        return self.units < 0

    def is_positive(self) -> bool:
        return self.units > 0

    def sign(self) -> int:
        return (self.units > 0) - (self.units < 0)

    def major(self) -> int:
        return abs(self.units) // currency_module.get(self.currency).minor_per_major()

    def minor(self) -> int:
        return abs(self.units) % currency_module.get(self.currency).minor_per_major()

    def format(self, with_symbol: bool = True) -> str:
        spec = currency_module.get(self.currency)
        sign = "-" if self.units < 0 else ""
        whole = self.major()
        if spec.exponent == 0:
            body = str(whole)
        else:
            frac = str(self.minor()).rjust(spec.exponent, "0")
            body = f"{whole}.{frac}"
        if with_symbol:
            return f"{sign}{spec.symbol}{body}"
        return f"{sign}{body} {self.currency}"

    def __str__(self) -> str:
        return self.format(with_symbol=False)

    def __repr__(self) -> str:
        return f"Money.from_minor({self.units}, {self.currency!r})"


def _parse_decimal(text: str, spec: currency_module.Currency) -> int:
    raw = text.strip()
    if not raw:
        raise Refused("an empty string is not an amount of money")
    negative = False
    if raw[0] in "+-":
        negative = raw[0] == "-"
        raw = raw[1:]
    if "," in raw:
        raise Refused(
            f"the amount {text!r} carries a thousands separator; the "
            "canonical parser takes plain digits and one decimal point"
        )
    if raw.count(".") > 1:
        raise Refused(f"the amount {text!r} has more than one decimal point")
    whole_text, _, frac_text = raw.partition(".")
    whole_text = whole_text or "0"
    if not whole_text.isdigit() or (frac_text and not frac_text.isdigit()):
        raise Refused(f"the amount {text!r} is not a plain decimal number")
    if len(frac_text) > spec.exponent:
        raise Refused(
            f"the amount {text!r} has more decimal places than {spec.code} "
            f"has minor units; {spec.code} carries {spec.exponent} of them"
        )
    frac_text = frac_text.ljust(spec.exponent, "0")
    units = int(whole_text) * spec.minor_per_major() + int(frac_text or "0")
    return -units if negative else units
