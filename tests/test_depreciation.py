from __future__ import annotations

from fractions import Fraction

import pytest

from mint.depreciation import declining_balance, straight_line, sum_of_years_digits
from mint.errors import Refused
from mint.money import Money

COST = Money.of(10000, "USD")
SALVAGE = Money.of(1000, "USD")


class TestStraightLine:
    def test_it_spreads_the_base_evenly(self):
        sched = straight_line(COST, SALVAGE, 5)
        assert sched.rows[0].depreciation == 180000  # 9000 / 5 = 1800.00
        assert sched.ending_book_value() == 100000  # salvage 1000.00

    def test_total_depreciation_equals_the_base(self):
        sched = straight_line(COST, SALVAGE, 5)
        assert sched.total_depreciation() == Money.of(9000, "USD")


class TestDecliningBalance:
    def test_it_front_loads_and_ends_on_salvage(self):
        sched = declining_balance(COST, SALVAGE, 5)
        assert sched.rows[0].depreciation == 400000  # 40% of 10000.00
        assert sched.ending_book_value() == 100000
        assert sched.rows[0].depreciation > sched.rows[-1].depreciation

    def test_it_never_dips_below_salvage(self):
        sched = declining_balance(COST, SALVAGE, 5)
        assert all(row.book_value >= 100000 for row in sched.rows)


class TestSumOfYears:
    def test_it_front_loads_toward_the_first_year(self):
        sched = sum_of_years_digits(COST, SALVAGE, 5)
        # first year weight 5/15 of 9000 = 3000.00.
        assert sched.rows[0].depreciation == 300000
        assert sched.ending_book_value() == 100000

    def test_total_matches_the_base(self):
        sched = sum_of_years_digits(COST, SALVAGE, 5)
        assert sched.total_depreciation() == Money.of(9000, "USD")


class TestRefusals:
    def test_salvage_above_cost_is_refused(self):
        with pytest.raises(Refused):
            straight_line(Money.of(100, "USD"), Money.of(200, "USD"), 5)

    def test_zero_life_is_refused(self):
        with pytest.raises(Refused):
            declining_balance(COST, SALVAGE, 0, Fraction(2))
