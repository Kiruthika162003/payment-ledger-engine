"""Formatting money for people: grouping, symbol placement, and how to show a loss.

Printing money is where a correct ledger goes wrong in public. The
same amount is written differently in different places, and the
differences are not decoration: the separators swap roles, so a
figure written 1.234,56 in one convention means the same as
1,234.56 in another and a system that mixes them misreads by a
factor of a thousand. The symbol goes before the number in some
places and after it in others, sometimes with a space that is part
of the convention rather than a typo. Negative amounts appear with
a minus, or in parentheses in accounting statements, where a
bracketed figure is the signal an auditor's eye is trained to
catch. This module makes each of those an explicit setting rather
than a hardcoded assumption, and formats from the integer minor
units so no formatting step can introduce a rounding error. Parsing
is offered as the exact inverse for the formats it produces, and
refuses anything it cannot read rather than guessing which
separator was meant, since guessing is precisely the thousand-fold
error the conventions invite.
"""

from __future__ import annotations

from dataclasses import dataclass

from mint import currency as currency_module
from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class Format:
    group_separator: str = ","
    decimal_separator: str = "."
    symbol_before: bool = True
    symbol_space: bool = False
    accounting_negatives: bool = False
    show_symbol: bool = True

    def __post_init__(self) -> None:
        if self.group_separator == self.decimal_separator:
            raise Refused(
                "the group and decimal separators must differ, or the figure "
                "cannot be read back"
            )
        if self.decimal_separator.isdigit() or self.group_separator.isdigit():
            raise Refused("a separator cannot be a digit")


US = Format()
EUROPEAN = Format(group_separator=".", decimal_separator=",", symbol_before=False,
                  symbol_space=True)
ACCOUNTING = Format(accounting_negatives=True)
PLAIN = Format(show_symbol=False, group_separator="")


def _group(digits: str, separator: str) -> str:
    if not separator:
        return digits
    out: list[str] = []
    for index, char in enumerate(reversed(digits)):
        if index and index % 3 == 0:
            out.append(separator)
        out.append(char)
    return "".join(reversed(out))


def format_money(amount: Money, style: Format = US) -> str:
    spec = currency_module.get(amount.currency)
    negative = amount.is_negative()
    whole = _group(str(amount.major()), style.group_separator)
    if spec.exponent == 0:
        body = whole
    else:
        body = whole + style.decimal_separator + str(amount.minor()).rjust(
            spec.exponent, "0"
        )
    if style.show_symbol:
        gap = " " if style.symbol_space else ""
        body = (
            f"{spec.symbol}{gap}{body}"
            if style.symbol_before
            else f"{body}{gap}{spec.symbol}"
        )
    if not negative:
        return body
    if style.accounting_negatives:
        return f"({body})"
    return f"-{body}"


def parse_money(text: str, currency: str, style: Format = US) -> Money:
    spec = currency_module.get(currency)
    raw = text.strip()
    if not raw:
        raise Refused("an empty string is not an amount")
    negative = False
    if raw.startswith("(") and raw.endswith(")"):
        negative = True
        raw = raw[1:-1].strip()
    elif raw.startswith("-"):
        negative = True
        raw = raw[1:].strip()
    raw = raw.replace(spec.symbol, "").strip()
    if style.group_separator:
        raw = raw.replace(style.group_separator, "")
    whole, separator, fraction = raw.partition(style.decimal_separator)
    if separator and spec.exponent == 0:
        raise Refused(
            f"{spec.code} has no minor unit, so {text!r} cannot carry a decimal part"
        )
    if not whole.isdigit() or (fraction and not fraction.isdigit()):
        raise Refused(
            f"the value {text!r} is not a number in this format; guessing which "
            "separator was meant is how a figure is misread by a thousand"
        )
    if len(fraction) > spec.exponent:
        raise Refused(f"{text!r} has more decimals than {spec.code} carries")
    units = int(whole) * spec.minor_per_major() + int(
        fraction.ljust(spec.exponent, "0") or "0"
    )
    return Money.from_minor(-units if negative else units, currency)


def round_trips(amount: Money, style: Format = US) -> bool:
    return parse_money(format_money(amount, style), amount.currency, style) == amount
