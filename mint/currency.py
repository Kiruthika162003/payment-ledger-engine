"""Currencies: the exponent that says where the decimal point lives.

The single fact a money type cannot do without is how many minor
units make one major unit of a currency, and that fact is not the
constant everyone assumes. Most currencies split into hundredths,
so a dollar is a hundred cents and the exponent is two, but the
yen and the won have no minor unit at all and their exponent is
zero, while the dinar of Bahrain, Kuwait, and several of its
neighbors splits into a thousand fils and carries an exponent of
three. A ledger that hardcodes two decimal places posts a yen
amount a hundred times too large and a dinar amount ten times too
small, so this registry keeps the exponent per currency and every
amount is stored in that currency's own smallest unit as a whole
number. A few currencies also round cash differently from their
minor unit: the Swiss franc has hundredths on paper but rounds
physical cash to the nearest five centimes, so the registry
records a cash-rounding increment separately from the exponent,
and code that pays out physical money rounds to the increment
while code that posts to an account keeps the full minor unit.
The registry ships with the currencies the tests and examples
exercise and refuses an unknown code by name rather than assuming
two decimals, because a silent assumption here is a silent factor
of ten in someone's money.
"""

from __future__ import annotations

from dataclasses import dataclass

from mint.errors import UnknownCurrency


@dataclass(frozen=True)
class Currency:
    code: str
    exponent: int
    symbol: str
    name: str
    cash_increment: int = 1

    def minor_per_major(self) -> int:
        return 10**self.exponent


_REGISTRY: dict[str, Currency] = {}


def register(currency: Currency) -> Currency:
    _REGISTRY[currency.code] = currency
    return currency


def get(code: str) -> Currency:
    key = code.upper()
    if key not in _REGISTRY:
        raise UnknownCurrency(
            f"the currency {code!r} is not in the registry; register it "
            "with its minor-unit exponent before posting amounts in it"
        )
    return _REGISTRY[key]


def is_known(code: str) -> bool:
    return code.upper() in _REGISTRY


def all_codes() -> list[str]:
    return sorted(_REGISTRY)


def _seed() -> None:
    for currency in (
        Currency("USD", 2, "$", "US Dollar"),
        Currency("EUR", 2, "€", "Euro"),
        Currency("GBP", 2, "£", "Pound Sterling"),
        Currency("JPY", 0, "¥", "Yen"),
        Currency("KRW", 0, "₩", "Won"),
        Currency("CHF", 2, "CHF", "Swiss Franc", cash_increment=5),
        Currency("BHD", 3, "BD", "Bahraini Dinar"),
        Currency("KWD", 3, "KD", "Kuwaiti Dinar"),
        Currency("INR", 2, "₹", "Indian Rupee"),
        Currency("CAD", 2, "$", "Canadian Dollar"),
        Currency("AUD", 2, "$", "Australian Dollar"),
        Currency("SEK", 2, "kr", "Swedish Krona"),
    ):
        register(currency)


_seed()
