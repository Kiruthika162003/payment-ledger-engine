"""Gifts in kind: donated goods and services, and the ones that may not be counted.

A charity given a van has received something real and records it at
what it would have cost to buy, because ignoring it understates both
the charity's income and the resources it actually deployed.
Donated services are the harder case and the rule is deliberately
narrow: they are recognized only when they require a specialist
skill, would have been bought in if not donated, and are provided by
someone who has that skill. An accountant donating an audit
qualifies; a hundred volunteers stuffing envelopes does not, and the
distinction exists because valuing general volunteering would let a
charity inflate its reported income without limit by counting hours
nobody would ever have paid for. This module applies the three-part
test and refuses a valuation that fails it, reporting the hours
anyway as a separate non-financial figure, since volunteering is
worth reporting even where it is not worth recognizing.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


@dataclass(frozen=True)
class DonatedGoods:
    description: str
    fair_value: Money
    received_on: datetime.date

    def __post_init__(self) -> None:
        if not self.fair_value.is_positive():
            raise Refused("donated goods are recorded at a positive fair value")
        if not self.description.strip():
            raise Refused("donated goods need a description")


@dataclass(frozen=True)
class DonatedService:
    description: str
    hours: Fraction
    hourly_rate: Money
    requires_specialist_skill: bool
    would_have_been_purchased: bool
    provider_has_the_skill: bool

    def __post_init__(self) -> None:
        if self.hours <= 0:
            raise Refused("a donated service covers positive hours")
        if self.hourly_rate.is_negative():
            raise Refused("an hourly rate is not negative")

    def meets_the_test(self) -> bool:
        # All three, not any of them: the narrowness is the whole point.
        return (
            self.requires_specialist_skill
            and self.would_have_been_purchased
            and self.provider_has_the_skill
        )

    def failed_conditions(self) -> list[str]:
        missing: list[str] = []
        if not self.requires_specialist_skill:
            missing.append("it does not require a specialist skill")
        if not self.would_have_been_purchased:
            missing.append("it would not have been bought in")
        if not self.provider_has_the_skill:
            missing.append("the provider does not hold that skill")
        return missing

    def value(self) -> Money:
        if not self.meets_the_test():
            raise Refused(
                f"the service {self.description!r} cannot be valued because "
                + " and ".join(self.failed_conditions())
                + "; counting it would let reported income grow without limit"
            )
        return round_money(
            self.hourly_rate.times(self.hours),
            self.hourly_rate.currency,
            Rounding.HALF_EVEN,
        )


@dataclass
class InKindRegister:
    currency: str
    goods: list[DonatedGoods] = field(default_factory=list)
    services: list[DonatedService] = field(default_factory=list)

    def receive_goods(self, item: DonatedGoods) -> DonatedGoods:
        if item.fair_value.currency != self.currency:
            raise Refused(
                f"a gift valued in {item.fair_value.currency} does not belong "
                f"to a {self.currency} register"
            )
        self.goods.append(item)
        return item

    def receive_service(self, item: DonatedService) -> DonatedService:
        if item.hourly_rate.currency != self.currency:
            raise Refused(
                f"a service rated in {item.hourly_rate.currency} does not "
                f"belong to a {self.currency} register"
            )
        self.services.append(item)
        return item

    def recognizable_services(self) -> list[DonatedService]:
        return [item for item in self.services if item.meets_the_test()]

    def unrecognizable_services(self) -> list[DonatedService]:
        return [item for item in self.services if not item.meets_the_test()]

    def goods_income(self) -> Money:
        total = Money.zero(self.currency)
        for item in self.goods:
            total = total + item.fair_value
        return total

    def services_income(self) -> Money:
        total = Money.zero(self.currency)
        for item in self.recognizable_services():
            total = total + item.value()
        return total

    def total_in_kind_income(self) -> Money:
        return self.goods_income() + self.services_income()

    def volunteer_hours(self) -> Fraction:
        # Reported as a number of hours rather than a value: worth reporting
        # even where it is not worth recognizing.
        total = Fraction(0)
        for item in self.unrecognizable_services():
            total += item.hours
        return total

    def recognized_hours(self) -> Fraction:
        total = Fraction(0)
        for item in self.recognizable_services():
            total += item.hours
        return total
