from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.pricing import PriceTable, PricingModel, Tier


def _tiers():
    return (
        Tier(up_to=100, unit_price=Money.from_minor(10, "USD")),
        Tier(up_to=None, unit_price=Money.from_minor(5, "USD")),
    )


class TestGraduated:
    def test_each_unit_pays_its_own_tier(self):
        table = PriceTable(_tiers(), PricingModel.GRADUATED)
        # 100 at 0.10 = 10.00, then 50 at 0.05 = 2.50.
        assert table.price(150) == Money.of("12.50", "USD")

    def test_within_the_first_tier_it_is_simple(self):
        table = PriceTable(_tiers(), PricingModel.GRADUATED)
        assert table.price(50) == Money.of("5.00", "USD")


class TestVolume:
    def test_every_unit_pays_the_reached_tier(self):
        table = PriceTable(_tiers(), PricingModel.VOLUME)
        # All 150 at 0.05 = 7.50, cheaper than graduated.
        assert table.price(150) == Money.of("7.50", "USD")

    def test_the_two_models_genuinely_differ(self):
        graduated = PriceTable(_tiers(), PricingModel.GRADUATED).price(150)
        volume = PriceTable(_tiers(), PricingModel.VOLUME).price(150)
        assert graduated != volume
        assert graduated > volume


class TestFlat:
    def test_flat_ignores_quantity(self):
        table = PriceTable(_tiers(), PricingModel.FLAT)
        assert table.price(1000) == Money.from_minor(10, "USD")


class TestEdges:
    def test_zero_quantity_costs_nothing(self):
        table = PriceTable(_tiers(), PricingModel.GRADUATED)
        assert table.price(0).is_zero()

    def test_a_negative_quantity_is_refused(self):
        with pytest.raises(Refused):
            PriceTable(_tiers(), PricingModel.GRADUATED).price(-1)

    def test_the_effective_unit_price_falls_with_volume(self):
        table = PriceTable(_tiers(), PricingModel.GRADUATED)
        assert table.effective_unit_price(50) == Fraction(10)
        assert table.effective_unit_price(1000) < Fraction(10)

    def test_no_effective_price_at_zero(self):
        table = PriceTable(_tiers(), PricingModel.GRADUATED)
        assert table.effective_unit_price(0) is None


class TestConstruction:
    def test_the_last_tier_must_be_open_ended(self):
        with pytest.raises(Refused) as caught:
            PriceTable(
                (Tier(up_to=100, unit_price=Money.from_minor(10, "USD")),),
                PricingModel.GRADUATED,
            )
        assert "larger than the table anticipated" in str(caught.value)

    def test_only_the_last_tier_may_be_open_ended(self):
        with pytest.raises(Refused):
            PriceTable(
                (
                    Tier(up_to=None, unit_price=Money.from_minor(10, "USD")),
                    Tier(up_to=None, unit_price=Money.from_minor(5, "USD")),
                ),
                PricingModel.GRADUATED,
            )

    def test_bounds_must_increase(self):
        with pytest.raises(Refused):
            PriceTable(
                (
                    Tier(up_to=100, unit_price=Money.from_minor(10, "USD")),
                    Tier(up_to=50, unit_price=Money.from_minor(8, "USD")),
                    Tier(up_to=None, unit_price=Money.from_minor(5, "USD")),
                ),
                PricingModel.GRADUATED,
            )

    def test_an_empty_table_is_refused(self):
        with pytest.raises(Refused):
            PriceTable((), PricingModel.GRADUATED)
