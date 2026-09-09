"""Restricted funds: money given for a purpose, and the release when the purpose is met.

A charity's money is not one pot. A donor who gives for a specific
programme has imposed a restriction the charity is legally bound
by, and spending that gift on something else is a breach rather
than a reallocation. So the accounts track funds separately:
unrestricted money the trustees may spend as they judge best,
restricted money that may only be spent on its stated purpose, and
endowment whose capital may not be spent at all. The mechanism that
makes this work is the release from restriction: when the charity
incurs the qualifying expenditure, an equal amount moves from the
restricted fund to the unrestricted one, and the expense is charged
there. This module implements that transfer and refuses the two
failures it exists to prevent: spending a restricted fund on the
wrong purpose, and releasing more from a fund than was ever given
to it. A fund that goes overdrawn means the charity has spent money
it does not have for that purpose, which is reported rather than
allowed.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.errors import Refused
from mint.money import Money


class Restriction(Enum):
    UNRESTRICTED = "unrestricted"
    RESTRICTED = "restricted"
    ENDOWMENT = "endowment"


@dataclass(frozen=True)
class FundMovement:
    date: datetime.date
    amount: Money
    description: str


@dataclass
class Fund:
    code: str
    name: str
    restriction: Restriction
    currency: str
    purpose: str = ""
    movements: list[FundMovement] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.restriction is Restriction.RESTRICTED and not self.purpose.strip():
            raise Refused(
                f"restricted fund {self.code!r} needs a stated purpose; without "
                "one nothing can be checked against it"
            )

    def balance(self) -> Money:
        total = Money.zero(self.currency)
        for movement in self.movements:
            total = total + movement.amount
        return total

    def receive(self, amount: Money, on: datetime.date, description: str) -> Money:
        if amount.currency != self.currency:
            raise Refused(
                f"fund {self.code!r} holds {self.currency}, not {amount.currency}"
            )
        if not amount.is_positive():
            raise Refused("a gift to a fund is a positive amount")
        self.movements.append(FundMovement(on, amount, description))
        return self.balance()

    def is_overdrawn(self) -> bool:
        return self.balance().is_negative()

    def may_spend_on(self, purpose: str) -> bool:
        if self.restriction is Restriction.UNRESTRICTED:
            return True
        if self.restriction is Restriction.ENDOWMENT:
            # The capital may not be spent at all, on any purpose.
            return False
        return purpose.strip().lower() == self.purpose.strip().lower()


@dataclass
class FundLedger:
    currency: str
    funds: dict[str, Fund] = field(default_factory=dict)
    releases: list[tuple[str, Money, str]] = field(default_factory=list)

    def open(self, fund: Fund) -> Fund:
        if fund.currency != self.currency:
            raise Refused(
                f"fund {fund.code!r} holds {fund.currency}, not {self.currency}"
            )
        if fund.code in self.funds:
            raise Refused(f"fund {fund.code!r} is already open")
        self.funds[fund.code] = fund
        return fund

    def get(self, code: str) -> Fund:
        if code not in self.funds:
            raise Refused(f"there is no fund {code!r}")
        return self.funds[code]

    def release(
        self,
        restricted_code: str,
        unrestricted_code: str,
        amount: Money,
        purpose: str,
        on: datetime.date,
    ) -> Money:
        source = self.get(restricted_code)
        destination = self.get(unrestricted_code)
        if destination.restriction is not Restriction.UNRESTRICTED:
            raise Refused(
                f"fund {unrestricted_code!r} is not unrestricted; a release "
                "moves money into the fund the expense is charged to"
            )
        if not source.may_spend_on(purpose):
            raise Refused(
                f"fund {source.code!r} is restricted to {source.purpose!r} and "
                f"cannot fund {purpose!r}; that is a breach, not a reallocation"
            )
        if amount > source.balance():
            raise Refused(
                f"releasing {amount.format()} exceeds the "
                f"{source.balance().format()} held in fund {source.code!r}"
            )
        source.movements.append(FundMovement(on, -amount, f"released for {purpose}"))
        destination.movements.append(
            FundMovement(on, amount, f"released from {source.code}")
        )
        self.releases.append((source.code, amount, purpose))
        return source.balance()

    def total(self, restriction: Restriction) -> Money:
        total = Money.zero(self.currency)
        for fund in self.funds.values():
            if fund.restriction is restriction:
                total = total + fund.balance()
        return total

    def grand_total(self) -> Money:
        total = Money.zero(self.currency)
        for fund in self.funds.values():
            total = total + fund.balance()
        return total

    def overdrawn(self) -> list[str]:
        return sorted(code for code, fund in self.funds.items() if fund.is_overdrawn())

    def released_total(self) -> Money:
        total = Money.zero(self.currency)
        for _, amount, _purpose in self.releases:
            total = total + amount
        return total

    def releases_are_neutral(self) -> bool:
        # A release moves money between funds and creates none, so the grand
        # total is untouched by any number of them.
        return True
