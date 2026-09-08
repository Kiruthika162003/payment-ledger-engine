from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.provisiondiscount import DiscountedProvision


def _provision(**kwargs) -> DiscountedProvision:
    base = {
        "id": "P-1",
        "undiscounted": Money.of(100000, "USD"),
        "rate": Fraction(5, 100),
        "periods": 10,
    }
    base.update(kwargs)
    return DiscountedProvision(**base)


class TestPresentValue:
    def test_a_future_cost_is_carried_below_its_face(self):
        provision = _provision()
        assert provision.present_value() < provision.undiscounted
        assert provision.carrying == provision.present_value()

    def test_the_discount_taken_is_reported(self):
        provision = _provision()
        assert provision.discount_taken().is_positive()

    def test_a_zero_rate_leaves_it_undiscounted(self):
        provision = _provision(rate=Fraction(0))
        assert provision.present_value() == provision.undiscounted
        assert provision.discount_taken().is_zero()

    def test_a_longer_wait_discounts_further(self):
        near = _provision(periods=2)
        far = _provision(periods=20)
        assert far.present_value() < near.present_value()


class TestUnwinding:
    def test_each_period_adds_a_finance_cost(self):
        provision = _provision()
        cost = provision.unwind()
        assert cost.is_positive()
        assert provision.carrying > provision.present_value()

    def test_it_lands_exactly_on_the_outflow(self):
        provision = _provision()
        provision.unwind_fully()
        assert provision.is_fully_unwound()
        assert provision.lands_on_the_outflow()
        assert provision.carrying == Money.of(100000, "USD")

    def test_the_total_finance_cost_equals_the_discount(self):
        provision = _provision()
        total = provision.unwind_fully()
        assert total == provision.discount_taken()

    def test_an_awkward_amount_still_lands_exactly(self):
        provision = _provision(undiscounted=Money.of("99999.99", "USD"), periods=7)
        provision.unwind_fully()
        assert provision.lands_on_the_outflow()

    def test_unwinding_past_the_term_is_refused(self):
        provision = _provision(periods=1)
        provision.unwind()
        with pytest.raises(Refused):
            provision.unwind()

    def test_the_steps_are_recorded(self):
        provision = _provision(periods=3)
        provision.unwind_fully()
        assert len(provision.steps) == 3
        assert provision.total_finance_cost() == provision.discount_taken()


class TestRemeasurement:
    def test_a_raised_estimate_increases_the_carrying_amount(self):
        provision = _provision()
        movement = provision.remeasure(undiscounted=Money.of(150000, "USD"))
        assert movement.is_positive()

    def test_a_higher_rate_lowers_it(self):
        provision = _provision()
        movement = provision.remeasure(rate=Fraction(10, 100))
        assert movement.is_negative()

    def test_remeasurement_is_reported_apart_from_unwinding(self):
        provision = _provision()
        unwind = provision.unwind()
        remeasure = provision.remeasure(undiscounted=Money.of(120000, "USD"))
        assert unwind != remeasure

    def test_a_negative_estimate_is_refused(self):
        with pytest.raises(Refused):
            _provision().remeasure(undiscounted=Money.zero("USD"))

    def test_a_negative_rate_is_refused(self):
        with pytest.raises(Refused):
            _provision().remeasure(rate=Fraction(-1, 100))


class TestConstruction:
    def test_a_nonpositive_provision_is_refused(self):
        with pytest.raises(Refused):
            _provision(undiscounted=Money.zero("USD"))

    def test_zero_periods_is_refused(self):
        with pytest.raises(Refused):
            _provision(periods=0)
