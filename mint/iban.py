"""IBAN validation: the mod-97 check that catches a mistyped account abroad.

An international bank account number carries its own two-digit
check, and the arithmetic behind it is unusual enough to be worth
stating plainly: move the first four characters to the end, replace
every letter with a two-digit number where A is ten and Z is
thirty-five, read the whole thing as one enormous integer, and a
valid IBAN leaves a remainder of exactly one when divided by
ninety-seven. The scheme catches every single-character error and
essentially every transposition, which matters more here than for
a domestic account because an international transfer to a wrong but
well-formed number can be genuinely hard to recall. This module
validates in that exact order and refuses rather than guesses when
the input is too short to have a country and check pair, or carries
characters outside the letters and digits an IBAN is made of. It
also computes the check digits for a country and account body,
which is what a test fixture needs to produce well-formed numbers
without copying real ones. Length varies by country and the
registry of lengths is data rather than logic, so the module
carries the lengths it knows and treats an unknown country as
valid-by-checksum rather than pretending to know better.
"""

from __future__ import annotations

from mint.errors import Refused

COUNTRY_LENGTHS = {
    "AD": 24, "AT": 20, "BE": 16, "BG": 22, "CH": 21, "CY": 28, "CZ": 24,
    "DE": 22, "DK": 18, "EE": 20, "ES": 24, "FI": 18, "FR": 27, "GB": 22,
    "GR": 27, "HR": 21, "HU": 28, "IE": 22, "IS": 26, "IT": 27, "LI": 21,
    "LT": 20, "LU": 20, "LV": 21, "MT": 31, "NL": 18, "NO": 15, "PL": 28,
    "PT": 25, "RO": 24, "SE": 24, "SI": 19, "SK": 24, "SM": 27,
}


def electronic_format(iban: str) -> str:
    return iban.replace(" ", "").replace("-", "").upper()


def _to_number(text: str) -> int:
    digits = []
    for char in text:
        if char.isdigit():
            digits.append(char)
        elif char.isalpha():
            digits.append(str(ord(char) - ord("A") + 10))
        else:
            raise Refused(
                f"the character {char!r} is not allowed in an IBAN; an IBAN is "
                "letters and digits only"
            )
    return int("".join(digits))


def remainder(iban: str) -> int:
    cleaned = electronic_format(iban)
    if len(cleaned) < 5:
        raise Refused(
            f"the value {iban!r} is too short to be an IBAN; it needs a country "
            "code, two check digits, and an account body"
        )
    rearranged = cleaned[4:] + cleaned[:4]
    return _to_number(rearranged) % 97


def is_valid(iban: str) -> bool:
    cleaned = electronic_format(iban)
    try:
        if remainder(cleaned) != 1:
            return False
    except Refused:
        return False
    expected = COUNTRY_LENGTHS.get(cleaned[:2])
    return expected is None or len(cleaned) == expected


def check_digits(country: str, body: str) -> str:
    country = country.upper()
    if len(country) != 2 or not country.isalpha():
        raise Refused("a country code is two letters")
    rearranged = electronic_format(body) + country + "00"
    value = 98 - (_to_number(rearranged) % 97)
    return f"{value:02d}"


def build(country: str, body: str) -> str:
    return f"{country.upper()}{check_digits(country, body)}{electronic_format(body)}"
