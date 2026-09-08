from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.aging import AgingItem, age
from mint.errors import Refused
from mint.money import Money
from mint.provision import provision_for

AS_OF = datetime.date(2026, 4, 1)

RATES = {
    "current": Fraction(0),
    "1-30": Fraction(2, 100),
    "31-60": Fraction(10, 100),
    "61-90": Fraction(25, 100),
    ">90": Fraction(1, 2),
}


def _report():
    items = [
        AgingItem("A", Money.of(1000, "USD"), datetime.date(2026, 5, 1)),
        AgingItem("B", Money.of(1000, "USD"), datetime.date(2026, 3, 20)),
        AgingItem("C", Money.of(1000, "USD"), datetime.date(2026, 1, 1)),
    ]
    return age(items, AS_OF, "USD")


class TestRequired:
    def test_the_allowance_weights_each_bucket(self):
        # A is not yet due (current, 0). B is 12 days over (1-30 at 2% of
        # 1000 = 20). C is exactly 90 days over, which lands in 61-90 by the
        # inclusive upper edge, not >90, so it provides 25% of 1000 = 250.
        prov = provision_for(_report(), RATES, Money.zero("USD"))
        assert prov.required == Money.of(270, "USD")

    def test_a_bucket_with_no_rate_provides_nothing(self):
        prov = provision_for(_report(), {"current": Fraction(0)}, Money.zero("USD"))
        assert prov.required.is_zero()


class TestMovement:
    def test_the_expense_is_the_increase_not_the_whole_allowance(self):
        # Required is 270 and 150 is already provided, so the period is
        # charged 120, not the full 270 again.
        prov = provision_for(_report(), RATES, Money.of(150, "USD"))
        assert prov.movement() == Money.of(120, "USD")

    def test_an_over_provided_allowance_releases(self):
        prov = provision_for(_report(), RATES, Money.of(400, "USD"))
        assert prov.is_release()
        assert prov.movement() == Money.of("-130.00", "USD")


class TestRefusals:
    def test_a_rate_above_one_is_refused(self):
        with pytest.raises(Refused) as caught:
            provision_for(_report(), {"current": Fraction(2)}, Money.zero("USD"))
        assert "cannot lose more than it holds" in str(caught.value)

    def test_a_negative_rate_is_refused(self):
        with pytest.raises(Refused):
            provision_for(_report(), {"current": Fraction(-1, 10)}, Money.zero("USD"))
