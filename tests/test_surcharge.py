from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.surcharge import Surcharge, SurchargeBase, SurchargeSchedule


class TestApplication:
    def test_a_percentage_surcharge(self):
        schedule = SurchargeSchedule()
        schedule.add(Surcharge("service", percent=Fraction(10, 100)))
        result = schedule.apply(Money.of(100, "USD"))
        assert result.total == Money.of(110, "USD")
        assert result.added() == Money.of(10, "USD")

    def test_a_fixed_surcharge(self):
        schedule = SurchargeSchedule()
        schedule.add(Surcharge("small order", fixed=Money.of(5, "USD")))
        assert schedule.apply(Money.of(20, "USD")).total == Money.of(25, "USD")

    def test_each_line_is_reported(self):
        schedule = SurchargeSchedule()
        schedule.add(Surcharge("service", percent=Fraction(10, 100)))
        schedule.add(Surcharge("fuel", fixed=Money.of(3, "USD")))
        result = schedule.apply(Money.of(100, "USD"))
        assert result.line("service") == Money.of(10, "USD")
        assert result.line("fuel") == Money.of(3, "USD")


class TestBase:
    def test_original_base_does_not_compound(self):
        schedule = SurchargeSchedule()
        schedule.add(Surcharge("a", percent=Fraction(10, 100)))
        schedule.add(Surcharge("b", percent=Fraction(5, 100)))
        # Both on the original 100: 10 + 5 = 115.
        assert schedule.apply(Money.of(100, "USD")).total == Money.of(115, "USD")

    def test_running_base_compounds(self):
        schedule = SurchargeSchedule()
        schedule.add(Surcharge("a", percent=Fraction(10, 100)))
        schedule.add(
            Surcharge("b", percent=Fraction(5, 100), base=SurchargeBase.RUNNING)
        )
        # 100 + 10 = 110, then 5% of 110 = 5.50.
        assert schedule.apply(Money.of(100, "USD")).total == Money.of("115.50", "USD")


class TestCap:
    def test_a_cap_limits_a_percentage(self):
        schedule = SurchargeSchedule()
        schedule.add(
            Surcharge("card", percent=Fraction(3, 100), cap=Money.of(5, "USD"))
        )
        assert schedule.apply(Money.of(1000, "USD")).line("card") == Money.of(5, "USD")

    def test_below_the_cap_it_is_unaffected(self):
        schedule = SurchargeSchedule()
        schedule.add(
            Surcharge("card", percent=Fraction(3, 100), cap=Money.of(5, "USD"))
        )
        assert schedule.apply(Money.of(100, "USD")).line("card") == Money.of(3, "USD")

    def test_a_zero_cap_waives_the_fee(self):
        schedule = SurchargeSchedule()
        schedule.add(
            Surcharge("card", percent=Fraction(3, 100), cap=Money.zero("USD"))
        )
        assert schedule.apply(Money.of(1000, "USD")).total == Money.of(1000, "USD")


class TestRefusals:
    def test_a_surcharge_that_adds_nothing_is_refused(self):
        with pytest.raises(Refused) as caught:
            Surcharge("empty")
        assert "neither a rate nor an amount" in str(caught.value)

    def test_a_negative_rate_is_refused(self):
        with pytest.raises(Refused):
            Surcharge("bad", percent=Fraction(-1, 100))

    def test_an_unapplied_line_is_refused(self):
        schedule = SurchargeSchedule()
        schedule.add(Surcharge("service", percent=Fraction(10, 100)))
        with pytest.raises(Refused):
            schedule.apply(Money.of(100, "USD")).line("ghost")
