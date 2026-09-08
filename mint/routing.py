"""Routing numbers: the weighted checksum that guards a US bank transfer.

An ABA routing number is nine digits identifying a US financial
institution, and its last digit is a checksum under a weighting of
three, seven, one repeated across the nine positions: the weighted
sum must be a multiple of ten. The weights are not arbitrary; they
were chosen so the check catches every single-digit error and the
adjacent transpositions that dominate hand-keyed entry, which is
the whole point of putting a check digit on a number a teller used
to read aloud. This module validates the number, computes the
check digit for the first eight, and reports the Federal Reserve
district implied by the leading two digits, since that prefix is
structured rather than random and a number whose prefix falls in
the unassigned ranges is malformed no matter what its checksum
says. A number of the wrong length is refused by name rather than
padded or truncated, because a routing number that is eight digits
long is not a routing number missing a digit, it is a different
field entirely, and quietly fixing it would send money somewhere
nobody chose.
"""

from __future__ import annotations

from mint.errors import Refused

WEIGHTS = (3, 7, 1, 3, 7, 1, 3, 7, 1)


def _digits(number: str, expected: int) -> list[int]:
    cleaned = number.replace(" ", "").replace("-", "")
    if not cleaned.isdigit():
        raise Refused(f"the routing number {number!r} must be digits only")
    if len(cleaned) != expected:
        raise Refused(
            f"a routing number is {expected} digits; {number!r} has "
            f"{len(cleaned)}, which is a different field entirely"
        )
    return [int(char) for char in cleaned]


def weighted_sum(number: str) -> int:
    digits = _digits(number, 9)
    return sum(digit * weight for digit, weight in zip(digits, WEIGHTS, strict=True))


def is_valid(number: str) -> bool:
    try:
        return weighted_sum(number) % 10 == 0
    except Refused:
        return False


def check_digit(first_eight: str) -> int:
    digits = _digits(first_eight, 8)
    partial = sum(
        digit * weight for digit, weight in zip(digits, WEIGHTS[:8], strict=True)
    )
    return (10 - partial % 10) % 10


def complete(first_eight: str) -> str:
    return first_eight + str(check_digit(first_eight))


def federal_reserve_district(number: str) -> int:
    digits = _digits(number, 9)
    prefix = digits[0] * 10 + digits[1]
    if prefix <= 12:
        return prefix
    if 21 <= prefix <= 32:
        return prefix - 20
    if 61 <= prefix <= 72:
        return prefix - 60
    if prefix == 80:
        return 0
    raise Refused(
        f"the prefix {prefix:02d} falls outside the assigned routing ranges; "
        "the number is malformed whatever its checksum says"
    )
