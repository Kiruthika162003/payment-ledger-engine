from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.impairment import ImpairableAsset, RecoverableAmount
from mint.money import Money


def _asset(carrying: str = "100000.00") -> ImpairableAsset:
    return ImpairableAsset("A-1", Money.of(carrying, "USD"))


def _recoverable(fair: str, in_use: str) -> RecoverableAmount:
    return RecoverableAmount(Money.of(fair, "USD"), Money.of(in_use, "USD"))


class TestRecoverableAmount:
    def test_it_takes_the_higher_of_the_two(self):
        assert _recoverable("60000.00", "80000.00").amount() == Money.of(80000, "USD")

    def test_an_asset_still_earning_is_not_impaired_by_a_poor_market(self):
        recoverable = _recoverable("10000.00", "120000.00")
        assert _asset().test(recoverable).is_zero()

    def test_it_reports_which_measure_drove_it(self):
        assert _recoverable("60000.00", "80000.00").driven_by_use()
        assert not _recoverable("90000.00", "80000.00").driven_by_use()

    def test_a_negative_measure_is_refused(self):
        with pytest.raises(Refused):
            _recoverable("-1.00", "10.00")


class TestImpairing:
    def test_a_shortfall_writes_the_asset_down(self):
        asset = _asset()
        loss = asset.impair(_recoverable("60000.00", "70000.00"))
        assert loss == Money.of(30000, "USD")
        assert asset.carrying_value == Money.of(70000, "USD")
        assert asset.is_impaired()

    def test_an_unimpaired_asset_refuses_the_write_down(self):
        with pytest.raises(Refused) as caught:
            _asset().impair(_recoverable("110000.00", "120000.00"))
        assert "not impaired" in str(caught.value)

    def test_the_test_reports_the_shortfall_without_taking_it(self):
        asset = _asset()
        assert asset.test(_recoverable("60000.00", "70000.00")) == Money.of(30000, "USD")
        assert asset.carrying_value == Money.of(100000, "USD")


class TestReversal:
    def test_a_recovery_reverses_the_impairment(self):
        asset = _asset()
        asset.impair(_recoverable("60000.00", "70000.00"))
        taken, refused = asset.reverse(_recoverable("85000.00", "85000.00"))
        assert taken == Money.of(15000, "USD")
        assert refused.is_zero()
        assert asset.carrying_value == Money.of(85000, "USD")

    def test_a_reversal_is_capped_at_the_never_impaired_value(self):
        asset = _asset()
        asset.impair(_recoverable("60000.00", "70000.00"))
        taken, refused = asset.reverse(_recoverable("150000.00", "150000.00"))
        assert taken == Money.of(30000, "USD")
        assert refused == Money.of(50000, "USD")
        assert asset.carrying_value == Money.of(100000, "USD")

    def test_a_full_reversal_clears_the_impairment(self):
        asset = _asset()
        asset.impair(_recoverable("60000.00", "70000.00"))
        asset.reverse(_recoverable("150000.00", "150000.00"))
        assert not asset.is_impaired()

    def test_reversing_an_unimpaired_asset_is_refused(self):
        with pytest.raises(Refused):
            _asset().reverse(_recoverable("150000.00", "150000.00"))

    def test_reversing_without_a_recovery_is_refused(self):
        asset = _asset()
        asset.impair(_recoverable("60000.00", "70000.00"))
        with pytest.raises(Refused) as caught:
            asset.reverse(_recoverable("50000.00", "60000.00"))
        assert "has not recovered" in str(caught.value)


class TestDepreciationInteraction:
    def test_depreciation_lowers_the_reversal_ceiling_too(self):
        asset = _asset()
        asset.impair(_recoverable("60000.00", "70000.00"))
        asset.depreciate(Money.of(10000, "USD"))
        assert asset.reversal_ceiling() == Money.of(90000, "USD")
        _taken, refused = asset.reverse(_recoverable("150000.00", "150000.00"))
        assert asset.carrying_value == Money.of(90000, "USD")
        assert refused.is_positive()

    def test_depreciation_below_zero_is_refused(self):
        with pytest.raises(Refused):
            _asset("100.00").depreciate(Money.of(200, "USD"))

    def test_a_nonpositive_charge_is_refused(self):
        with pytest.raises(Refused):
            _asset().depreciate(Money.zero("USD"))
