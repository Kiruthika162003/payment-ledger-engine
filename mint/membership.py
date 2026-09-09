"""Memberships: a joining fee that is earned once and dues that are earned over a year.

A membership charges two different things and they are earned at
different speeds. The joining fee buys admission and is earned when
the member is admitted, since the organization has done what the
fee was for. The annual dues buy a year of membership and are
earned across that year, so a member who joins in October has
bought three months of this year and nine of the next, and an
organization that books the whole subscription on receipt reports
income it has not yet earned and must give back if the member
leaves. This module prorates the dues to the remaining part of the
year, recognizes them across it, and computes the refund owed on a
mid-year resignation, which is the unearned part and nothing else,
since the joining fee is not refundable once admission has been
given. A lapsed member who rejoins pays the joining fee again,
because they are being admitted again, which is the rule that makes
the fee mean something.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money
from mint.subscription import prorated_charge


class MemberState(Enum):
    ACTIVE = "active"
    LAPSED = "lapsed"
    RESIGNED = "resigned"


@dataclass
class Membership:
    id: str
    member: str
    joining_fee: Money
    annual_dues: Money
    joined_on: datetime.date
    year_start: datetime.date
    year_end: datetime.date
    state: MemberState = MemberState.ACTIVE
    dues_paid: Money | None = None
    ended_on: datetime.date | None = None
    history: list[tuple[datetime.date, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.annual_dues.same_currency(self.joining_fee)
        if not self.annual_dues.is_positive():
            raise Refused("annual dues are a positive amount")
        if self.joining_fee.is_negative():
            raise Refused("a joining fee is not negative")
        if self.year_end <= self.year_start:
            raise Refused("a membership year ends after it begins")
        if not self.year_start <= self.joined_on <= self.year_end:
            raise Refused("a member joins inside the membership year")
        if self.dues_paid is None:
            self.dues_paid = Money.zero(self.annual_dues.currency)

    def prorated_dues(self) -> Money:
        return prorated_charge(
            self.annual_dues, self.joined_on, self.year_start, self.year_end
        )

    def amount_due_on_joining(self) -> Money:
        return self.joining_fee + self.prorated_dues()

    def joining_fee_earned(self) -> Money:
        # Earned on admission: the organization has done what it was for.
        return self.joining_fee

    def dues_earned_to(self, as_of: datetime.date) -> Money:
        if as_of <= self.joined_on:
            return Money.zero(self.annual_dues.currency)
        end = min(as_of, self.year_end)
        span = (self.year_end - self.joined_on).days
        if span <= 0:
            return self.prorated_dues()
        elapsed = Fraction((end - self.joined_on).days, span)
        return round_money(
            self.prorated_dues().times(elapsed),
            self.annual_dues.currency,
            Rounding.HALF_EVEN,
        )

    def unearned_dues_at(self, as_of: datetime.date) -> Money:
        return self.prorated_dues() - self.dues_earned_to(as_of)

    def pay(self, amount: Money) -> Money:
        amount.same_currency(self.annual_dues)
        if self.state is MemberState.RESIGNED:
            raise Refused(f"membership {self.id!r} has been resigned")
        if not amount.is_positive():
            raise Refused("a membership payment is a positive amount")
        self.dues_paid = self.dues_paid + amount
        return self.dues_paid

    def refund_on_resignation(self, as_of: datetime.date) -> Money:
        # The unearned dues and nothing else: admission has been given.
        return self.unearned_dues_at(as_of)

    def resign(self, on: datetime.date) -> Money:
        if self.state is MemberState.RESIGNED:
            raise Refused(f"membership {self.id!r} is already resigned")
        refund = self.refund_on_resignation(on)
        self.state = MemberState.RESIGNED
        self.ended_on = on
        self.history.append((on, "resigned"))
        return refund

    def lapse(self, on: datetime.date) -> MemberState:
        if self.state is not MemberState.ACTIVE:
            raise Refused(f"membership {self.id!r} is {self.state.value}")
        if on <= self.year_end:
            raise Refused(
                f"membership {self.id!r} runs to {self.year_end.isoformat()} and "
                "has not lapsed yet"
            )
        self.state = MemberState.LAPSED
        self.history.append((on, "lapsed"))
        return self.state

    def rejoin_cost(self) -> Money:
        if self.state is MemberState.ACTIVE:
            raise Refused(f"membership {self.id!r} is still active")
        # The joining fee is charged again, because admission is being given
        # again, which is what makes the fee mean anything.
        return self.joining_fee + self.annual_dues

    def is_active(self) -> bool:
        return self.state is MemberState.ACTIVE
