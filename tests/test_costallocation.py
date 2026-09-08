from __future__ import annotations

from fractions import Fraction

import pytest

from mint.costallocation import AllocationRun, CostCentre, CostPool
from mint.errors import Refused
from mint.money import Money


def _run() -> AllocationRun:
    run = AllocationRun("USD")
    sales = run.add_centre(CostCentre("SLS", "Sales"))
    engineering = run.add_centre(CostCentre("ENG", "Engineering"))
    warehouse = run.add_centre(CostCentre("WHS", "Warehouse"))
    sales.set_driver("headcount", Fraction(10))
    engineering.set_driver("headcount", Fraction(30))
    warehouse.set_driver("headcount", Fraction(10))
    sales.set_driver("floor_area", Fraction(100))
    engineering.set_driver("floor_area", Fraction(300))
    warehouse.set_driver("floor_area", Fraction(600))
    run.add_pool(CostPool("HR", Money.of(50000, "USD"), "headcount"))
    run.add_pool(CostPool("Rent", Money.of(100000, "USD"), "floor_area"))
    return run


class TestAllocation:
    def test_a_pool_splits_by_its_driver(self):
        run = _run()
        shares = run.allocate_pool(run.pools[0])
        assert shares["ENG"] == Money.of(30000, "USD")
        assert shares["SLS"] == Money.of(10000, "USD")

    def test_a_different_driver_gives_a_different_split(self):
        run = _run()
        run.allocate_pool(run.pools[1])
        assert run.centres[2].allocated["Rent"] == 6000000

    def test_every_cent_lands_somewhere(self):
        run = _run()
        run.run()
        assert run.is_complete()
        assert run.allocated_total() == run.pool_total()

    def test_an_awkward_pool_still_conserves_the_cent(self):
        run = AllocationRun("USD")
        for index in range(3):
            centre = run.add_centre(CostCentre(f"C{index}", f"Centre {index}"))
            centre.set_driver("headcount", Fraction(1))
        run.add_pool(CostPool("Odd", Money.of("1000.01", "USD"), "headcount"))
        run.run()
        assert run.is_complete()


class TestZeroDrivers:
    def test_a_centre_with_no_driver_gets_nothing(self):
        run = _run()
        empty = run.add_centre(CostCentre("EMP", "Empty"))
        run.run()
        assert empty.total_allocated("USD").is_zero()

    def test_a_pool_with_no_eligible_centre_is_refused(self):
        run = _run()
        run.add_pool(CostPool("Mystery", Money.of(1000, "USD"), "unicorns"))
        with pytest.raises(Refused) as caught:
            run.run()
        assert "arbitrary charge" in str(caught.value)

    def test_eligibility_excludes_zero_values(self):
        run = _run()
        centre = run.add_centre(CostCentre("ZER", "Zero"))
        centre.set_driver("headcount", Fraction(0))
        assert centre not in run.eligible("headcount")


class TestShares:
    def test_the_share_of_each_centre_is_reported(self):
        run = _run()
        run.run()
        share = run.share_of("ENG")
        assert share is not None
        assert 0 < share < 1

    def test_shares_sum_to_one(self):
        run = _run()
        run.run()
        total = sum(run.share_of(centre.code) for centre in run.centres)
        assert total == 1

    def test_an_unknown_centre_is_refused(self):
        run = _run()
        run.run()
        with pytest.raises(Refused):
            run.share_of("NOPE")

    def test_no_share_before_anything_is_allocated(self):
        assert _run().share_of("ENG") is None


class TestConstruction:
    def test_a_duplicate_centre_is_refused(self):
        run = _run()
        with pytest.raises(Refused):
            run.add_centre(CostCentre("SLS", "Again"))

    def test_a_pool_without_a_driver_is_refused(self):
        with pytest.raises(Refused):
            CostPool("Bad", Money.of(100, "USD"), "  ")

    def test_a_nonpositive_pool_is_refused(self):
        with pytest.raises(Refused):
            CostPool("Bad", Money.zero("USD"), "headcount")

    def test_a_negative_driver_is_refused(self):
        with pytest.raises(Refused):
            CostCentre("X", "X").set_driver("headcount", Fraction(-1))

    def test_a_wrong_currency_pool_is_refused(self):
        run = _run()
        with pytest.raises(Refused):
            run.add_pool(CostPool("Euro", Money.of(100, "EUR"), "headcount"))
