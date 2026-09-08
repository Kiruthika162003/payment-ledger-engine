from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.fixedasset import AssetRegister, FixedAsset
from mint.money import Money

BOUGHT = datetime.date(2026, 1, 1)
SOLD = datetime.date(2029, 1, 1)


def _asset(**kwargs) -> FixedAsset:
    base = {
        "id": "A-1",
        "description": "Delivery van",
        "cost": Money.of(30000, "USD"),
        "acquired": BOUGHT,
        "life_years": 5,
        "salvage": Money.of(5000, "USD"),
    }
    base.update(kwargs)
    return FixedAsset(**base)


class TestCarryingValue:
    def test_a_new_asset_carries_its_cost(self):
        assert _asset().carrying_value() == Money.of(30000, "USD")

    def test_depreciation_reduces_the_carrying_value(self):
        asset = _asset()
        asset.depreciate()
        assert asset.carrying_value() == Money.of(25000, "USD")

    def test_the_annual_charge_spreads_the_base(self):
        assert _asset().annual_charge() == Money.of(5000, "USD")

    def test_it_never_depreciates_past_salvage(self):
        asset = _asset()
        for _ in range(5):
            asset.depreciate()
        assert asset.carrying_value() == Money.of(5000, "USD")
        assert asset.is_fully_depreciated()

    def test_a_fully_depreciated_asset_refuses_more(self):
        asset = _asset()
        for _ in range(5):
            asset.depreciate()
        with pytest.raises(Refused) as caught:
            asset.depreciate()
        assert "fully depreciated" in str(caught.value)


class TestDisposal:
    def test_a_gain_is_measured_against_carrying_value_not_cost(self):
        asset = _asset()
        for _ in range(3):
            asset.depreciate()
        # Carrying value is 15000; selling for 18000 is a 3000 gain even
        # though it cost 30000.
        gain = asset.dispose(Money.of(18000, "USD"), SOLD)
        assert asset.carrying_value() == Money.of(15000, "USD")
        assert gain == Money.of(3000, "USD")

    def test_a_loss_is_reported_as_negative(self):
        asset = _asset()
        for _ in range(3):
            asset.depreciate()
        assert asset.dispose(Money.of(12000, "USD"), SOLD).is_negative()

    def test_the_gain_is_available_afterward(self):
        asset = _asset()
        asset.depreciate()
        asset.dispose(Money.of(26000, "USD"), SOLD)
        assert asset.gain_on_disposal() == Money.of(1000, "USD")

    def test_a_disposed_asset_stops_depreciating(self):
        asset = _asset()
        asset.dispose(Money.of(1, "USD"), SOLD)
        with pytest.raises(Refused):
            asset.depreciate()

    def test_disposing_twice_is_refused(self):
        asset = _asset()
        asset.dispose(Money.of(1, "USD"), SOLD)
        with pytest.raises(Refused):
            asset.dispose(Money.of(1, "USD"), SOLD)

    def test_disposing_before_acquisition_is_refused(self):
        with pytest.raises(Refused):
            _asset().dispose(Money.of(1, "USD"), datetime.date(2025, 1, 1))


class TestRegister:
    def _register(self) -> AssetRegister:
        register = AssetRegister("USD")
        register.add(_asset())
        register.add(_asset(id="A-2", cost=Money.of(10000, "USD"),
                            salvage=Money.zero("USD")))
        return register

    def test_the_register_totals_cost_and_depreciation(self):
        register = self._register()
        assert register.total_cost() == Money.of(40000, "USD")
        register.charge_all()
        assert register.total_accumulated() == Money.of(7000, "USD")

    def test_net_book_value_is_the_difference(self):
        register = self._register()
        register.charge_all()
        assert register.net_book_value() == Money.of(33000, "USD")

    def test_a_disposed_asset_leaves_the_active_list_but_stays(self):
        register = self._register()
        register.get("A-1").dispose(Money.of(100, "USD"), SOLD)
        assert len(register.active()) == 1
        assert len(register.assets) == 2

    def test_a_duplicate_asset_is_refused(self):
        register = self._register()
        with pytest.raises(Refused):
            register.add(_asset())

    def test_a_wrong_currency_asset_is_refused(self):
        register = self._register()
        with pytest.raises(Refused):
            register.add(_asset(id="A-3", cost=Money.of(100, "EUR"),
                                salvage=Money.zero("EUR")))

    def test_an_unknown_asset_is_refused(self):
        with pytest.raises(Refused):
            self._register().get("A-9")


class TestConstruction:
    def test_salvage_above_cost_is_refused(self):
        with pytest.raises(Refused):
            _asset(salvage=Money.of(50000, "USD"))

    def test_zero_life_is_refused(self):
        with pytest.raises(Refused):
            _asset(life_years=0)
