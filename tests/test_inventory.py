from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.inventory import CostMethod, Inventory
from mint.money import Money


def _stocked(method: CostMethod) -> Inventory:
    inventory = Inventory(currency="USD", method=method)
    inventory.purchase(10, Money.of(10, "USD"))
    inventory.purchase(10, Money.of(20, "USD"))
    return inventory


class TestMethods:
    def test_fifo_costs_at_the_oldest_price(self):
        inventory = _stocked(CostMethod.FIFO)
        assert inventory.sell(10) == Money.of(100, "USD")

    def test_lifo_costs_at_the_newest_price(self):
        inventory = _stocked(CostMethod.LIFO)
        assert inventory.sell(10) == Money.of(200, "USD")

    def test_weighted_average_blends_the_lots(self):
        inventory = _stocked(CostMethod.WEIGHTED_AVERAGE)
        assert inventory.sell(10) == Money.of(150, "USD")

    def test_the_three_methods_genuinely_differ(self):
        costs = {
            method: _stocked(method).sell(10).units
            for method in CostMethod
        }
        assert len(set(costs.values())) == 3


class TestCrossingLots:
    def test_fifo_spans_two_lots(self):
        inventory = _stocked(CostMethod.FIFO)
        # All ten cheap units plus five dear ones: 100 + 100 = 200.
        assert inventory.sell(15) == Money.of(200, "USD")

    def test_lifo_spans_two_lots_the_other_way(self):
        inventory = _stocked(CostMethod.LIFO)
        # All ten dear units plus five cheap ones: 200 + 50 = 250.
        assert inventory.sell(15) == Money.of(250, "USD")


class TestReconciliation:
    def test_bought_equals_sold_plus_held(self):
        for method in CostMethod:
            inventory = _stocked(method)
            inventory.sell(7)
            inventory.sell(5)
            assert inventory.reconciles()

    def test_closing_value_falls_as_stock_sells(self):
        inventory = _stocked(CostMethod.FIFO)
        before = inventory.closing_value()
        inventory.sell(5)
        assert inventory.closing_value() < before

    def test_selling_everything_leaves_nothing(self):
        inventory = _stocked(CostMethod.FIFO)
        inventory.sell(20)
        assert inventory.on_hand() == 0
        assert inventory.closing_value().is_zero()


class TestRefusals:
    def test_selling_more_than_held_is_refused(self):
        inventory = _stocked(CostMethod.FIFO)
        with pytest.raises(Refused) as caught:
            inventory.sell(25)
        assert "not a cheaper way to trade" in str(caught.value)

    def test_a_zero_purchase_is_refused(self):
        with pytest.raises(Refused):
            _stocked(CostMethod.FIFO).purchase(0, Money.of(1, "USD"))

    def test_a_wrong_currency_purchase_is_refused(self):
        with pytest.raises(Refused):
            _stocked(CostMethod.FIFO).purchase(1, Money.of(1, "EUR"))

    def test_a_zero_sale_is_refused(self):
        with pytest.raises(Refused):
            _stocked(CostMethod.FIFO).sell(0)
