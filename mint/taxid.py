"""Tax identifiers: checking the shape of a number before a return is filed under it.

A tax identifier that is merely wrong in format will be rejected by
the authority weeks after filing, so validating the shape at the
point of entry is worth doing even though it proves nothing about
whether the number belongs to the party claiming it. The formats
differ enough that a single regular expression would be a lie: a
European VAT number begins with its country code and then follows
that country's own rule, several of which carry check digits, while
a US employer number is nine digits whose leading pair comes from
an assigned range. This module holds the per-country rules as data
and checks against them, returning what failed rather than a bare
false, since telling a user their number is invalid without saying
why produces a support ticket. A country the module does not know
is reported as unknown rather than valid or invalid, because
claiming to have validated something it cannot check is the one
answer that would actually be harmful.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mint.errors import Refused


class Verdict(Enum):
    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN_COUNTRY = "unknown_country"


@dataclass(frozen=True)
class IdCheck:
    identifier: str
    country: str
    verdict: Verdict
    reason: str = ""

    def is_valid(self) -> bool:
        return self.verdict is Verdict.VALID

    def is_checkable(self) -> bool:
        return self.verdict is not Verdict.UNKNOWN_COUNTRY


def normalize(identifier: str) -> str:
    return "".join(
        char for char in identifier.upper() if char.isalnum()
    )


def _digits_only(body: str, length: int) -> str | None:
    if len(body) != length:
        return f"expected {length} digits, found {len(body)}"
    if not body.isdigit():
        return "expected digits only"
    return None


def _gb_vat(body: str) -> str | None:
    if len(body) not in (9, 12):
        return "a UK VAT number is 9 or 12 digits"
    if not body.isdigit():
        return "expected digits only"
    weights = (8, 7, 6, 5, 4, 3, 2)
    total = sum(int(d) * w for d, w in zip(body[:7], weights, strict=True))
    remainder = total % 97
    check = int(body[7:9])
    if (remainder + check) % 97 != 0 and (remainder + check + 55) % 97 != 0:
        return "the check digits do not match the number"
    return None


def _de_vat(body: str) -> str | None:
    return _digits_only(body, 9)


def _fr_vat(body: str) -> str | None:
    if len(body) != 11:
        return "a French VAT number is 11 characters"
    if not body[2:].isdigit():
        return "the last nine characters are digits"
    return None


def _us_ein(body: str) -> str | None:
    problem = _digits_only(body, 9)
    if problem is not None:
        return problem
    prefix = int(body[:2])
    # The unassigned prefixes; a number using one is malformed.
    if prefix in (7, 8, 9, 17, 18, 19, 28, 29, 49, 78, 79, 89):
        return f"the prefix {body[:2]} is not an assigned range"
    return None


_RULES = {
    "GB": _gb_vat,
    "DE": _de_vat,
    "FR": _fr_vat,
    "US": _us_ein,
}


def check(identifier: str, country: str) -> IdCheck:
    if not identifier.strip():
        raise Refused("a tax identifier cannot be blank")
    code = country.strip().upper()
    if len(code) != 2 or not code.isalpha():
        raise Refused("a country code is two letters")
    cleaned = normalize(identifier)
    if cleaned.startswith(code):
        cleaned = cleaned[len(code) :]
    rule = _RULES.get(code)
    if rule is None:
        # Never claimed as valid: pretending to have checked would be worse
        # than admitting the rule is unknown.
        return IdCheck(
            identifier,
            code,
            Verdict.UNKNOWN_COUNTRY,
            f"no format rule is held for {code}",
        )
    problem = rule(cleaned)
    if problem is None:
        return IdCheck(identifier, code, Verdict.VALID)
    return IdCheck(identifier, code, Verdict.INVALID, problem)


def known_countries() -> list[str]:
    return sorted(_RULES)


def format_for_display(identifier: str, country: str) -> str:
    code = country.strip().upper()
    return f"{code}{normalize(identifier).removeprefix(code)}"
