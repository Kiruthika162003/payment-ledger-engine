from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.fees import FeeSchedule
from mint.money import Money


def _schedule() -> FeeSchedule:
    return FeeSchedule(percent=Fraction(29, 1000), fixed=Money.of("0.30", "USD"))


class TestCharge:
    def test_the_familiar_processor_fee(self):
        breakdown = _schedule().charge(Money.of(100, "USD"))
        assert breakdown.fee == Money.of("3.20", "USD")
        assert breakdown.net == Money.of("96.80", "USD")
        assert breakdown.reconciles()

    def test_a_fee_larger_than_the_charge_is_refused(self):
        schedule = FeeSchedule(percent=Fraction(1, 2), fixed=Money.of(10, "USD"))
        with pytest.raises(Refused) as caught:
            schedule.charge(Money.of(1, "USD"))
        assert "nets negative" in str(caught.value)


class TestGrossUp:
    def test_gross_up_leaves_the_merchant_whole(self):
        breakdown = _schedule().gross_for_net(Money.of(100, "USD"))
        assert breakdown.gross == Money.of("103.30", "USD")
        assert breakdown.net >= Money.of(100, "USD")

    def test_a_nonpositive_target_is_refused(self):
        with pytest.raises(Refused):
            _schedule().gross_for_net(Money.zero("USD"))


class TestConstruction:
    def test_a_percentage_at_or_above_one_is_refused(self):
        with pytest.raises(Refused):
            FeeSchedule(percent=Fraction(1), fixed=Money.zero("USD"))

    def test_a_negative_fixed_fee_is_refused(self):
        with pytest.raises(Refused):
            FeeSchedule(percent=Fraction(1, 100), fixed=Money.of("-1.00", "USD"))
