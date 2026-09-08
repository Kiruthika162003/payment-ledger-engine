"""Card references: brand, masking, and expiry, without ever holding a card number.

A ledger has no business storing card numbers, so this module works
with what a ledger legitimately keeps: the first six digits that
identify the issuing range, the last four that let a human
recognize their own card, and the expiry. From those it can name
the brand, render the masked form a receipt shows, and tell whether
the card has expired as of a date, which is all the payments layer
above it actually needs. The brand rules are prefix ranges rather
than lengths alone, since several brands share a length and only
the prefix distinguishes them. Expiry is the detail worth stating:
a card expires at the end of its stated month, not at the start, so
a card marked as expiring in March is valid throughout March and
invalid from the first of April, and treating the expiry date as
the first of the month declines a month of perfectly good cards.
The module refuses a masked reference whose last four are not four
digits rather than displaying whatever it was given, because a
receipt showing a mangled card reference is how a customer
concludes their details were mishandled.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from mint.calendarutil import days_in_month
from mint.errors import Refused

BRAND_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Visa", ("4",)),
    ("Mastercard", ("51", "52", "53", "54", "55", "2221", "2720")),
    ("American Express", ("34", "37")),
    ("Discover", ("6011", "65")),
    ("JCB", ("35",)),
    ("Diners Club", ("300", "301", "302", "303", "304", "305", "36", "38")),
)


def brand_for(bin_digits: str) -> str:
    cleaned = bin_digits.strip()
    if not cleaned.isdigit():
        raise Refused("an issuer range is digits only")
    for brand, prefixes in BRAND_RULES:
        for prefix in prefixes:
            if cleaned.startswith(prefix):
                return brand
    return "Unknown"


@dataclass(frozen=True)
class CardReference:
    bin_digits: str
    last_four: str
    expiry_year: int
    expiry_month: int
    holder: str = ""

    def __post_init__(self) -> None:
        if not self.last_four.isdigit() or len(self.last_four) != 4:
            raise Refused(
                "a card reference carries exactly four trailing digits; showing "
                "a mangled reference tells a customer their details were "
                "mishandled"
            )
        if not self.bin_digits.isdigit() or len(self.bin_digits) < 6:
            raise Refused("an issuer range is at least six digits")
        if not 1 <= self.expiry_month <= 12:
            raise Refused("an expiry month runs from one to twelve")
        if self.expiry_year < 1970:
            raise Refused("an expiry year that early is a data error")

    def brand(self) -> str:
        return brand_for(self.bin_digits)

    def masked(self, mask: str = "*") -> str:
        return f"{mask * 4} {mask * 4} {mask * 4} {self.last_four}"

    def expires_on(self) -> datetime.date:
        # The last day of the stated month: a card marked March is good
        # through March and declines from the first of April.
        last_day = days_in_month(self.expiry_year, self.expiry_month)
        return datetime.date(self.expiry_year, self.expiry_month, last_day)

    def is_expired(self, as_of: datetime.date) -> bool:
        return as_of > self.expires_on()

    def is_valid_on(self, as_of: datetime.date) -> bool:
        return not self.is_expired(as_of)

    def months_until_expiry(self, as_of: datetime.date) -> int:
        expiry = self.expires_on()
        return (expiry.year - as_of.year) * 12 + (expiry.month - as_of.month)

    def describe(self) -> str:
        return f"{self.brand()} ending {self.last_four}"
