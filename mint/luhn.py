"""The Luhn check: the one-digit guard that catches a mistyped card number.

Almost every payment card number carries a Luhn check digit, a
single trailing digit chosen so that a simple weighted sum of the
whole number is a multiple of ten. It is not security, it is a
typo catch: it detects every single-digit error and almost every
transposition of adjacent digits, which are the mistakes a human
keying a number actually makes, and catching them at the edge
saves a doomed authorization round-trip. This module computes the
checksum, validates a number, and derives the check digit for a
number that does not yet have one, so a system generating test
card references can make them well-formed. It works on the digits
and tolerates the spaces and dashes people type, stripping them
before counting, but it refuses a value with any other character
rather than silently skipping it, because a letter in a card
number is not a formatting quirk to ignore, it is a sign the field
holds something that is not a card number at all. This validates
the shape of a number only; it never stores or transmits one, in
keeping with the rule that real card data does not belong in a
ledger.
"""

from __future__ import annotations

from mint.errors import Refused


def _digits(number: str) -> list[int]:
    cleaned = number.replace(" ", "").replace("-", "")
    if not cleaned:
        raise Refused("an empty string is not a number to check")
    if not cleaned.isdigit():
        raise Refused(
            f"the value {number!r} has non-digit characters; a letter in a "
            "card number means the field holds something else"
        )
    return [int(char) for char in cleaned]


def checksum(number: str) -> int:
    digits = _digits(number)
    total = 0
    for position, digit in enumerate(reversed(digits)):
        if position % 2 == 1:
            doubled = digit * 2
            total += doubled - 9 if doubled > 9 else doubled
        else:
            total += digit
    return total % 10


def is_valid(number: str) -> bool:
    return checksum(number) == 0


def check_digit(partial: str) -> int:
    # The digit to append so the whole number passes: append a zero, take
    # the checksum, and the completing digit is ten minus it modulo ten.
    base = checksum(partial + "0")
    return (10 - base) % 10


def complete(partial: str) -> str:
    return partial + str(check_digit(partial))
