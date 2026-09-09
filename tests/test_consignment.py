from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.consignment import ConsignmentAccount
from mint.errors import Refused
from mint.money import Money

DAY = datetime.date(2026, 3, 1)


def _account(**kwargs) -> ConsignmentAccount:
    base = {
        "consignor": "maker",
        "consignee": "shop",
        "currency": "USD",
        "commission_rate": Fraction(20, 100),
    }
    base.update(kwargs)
    account = ConsignmentAccount(**base)
    account.ship(100, Money.of(6, "USD"), DAY)
    return account


class TestOwnership:
    def test_the_consignee_carries_no_inventory(self):
        assert _account().consignee_inventory().is_zero()

    def test_the_consignor_still_carries_it(self):
        assert _account().consignor_inventory() == Money.of(600, "USD")

    def test_selling_moves_goods_out_of_the_pool(self):
        account = _account()
        account.sell(40, Money.of(10, "USD"), DAY)
        assert account.units_on_hand() == 60
        assert account.consignor_inventory() == Money.of(360, "USD")

    def test_the_units_reconcile(self):
        account = _account()
        account.sell(30, Money.of(10, "USD"), DAY)
        account.send_back(20, DAY)
        assert account.units_shipped() == 100
        assert account.units_sold() == 30
        assert account.units_returned() == 20
        assert account.units_on_hand() == 50


class TestSale:
    def test_the_consignee_earns_only_a_commission(self):
        account = _account()
        sale = account.sell(50, Money.of(10, "USD"), DAY)
        assert sale.gross() == Money.of(500, "USD")
        assert sale.commission == Money.of(100, "USD")
        assert account.consignee_revenue() == Money.of(100, "USD")

    def test_the_consignor_recognizes_the_whole_sale(self):
        account = _account()
        account.sell(50, Money.of(10, "USD"), DAY)
        assert account.consignor_revenue() == Money.of(500, "USD")

    def test_the_sale_reconciles(self):
        account = _account()
        assert account.sell(50, Money.of(10, "USD"), DAY).reconciles()

    def test_the_amount_owed_to_the_consignor(self):
        account = _account()
        account.sell(50, Money.of(10, "USD"), DAY)
        assert account.amount_due_to_consignor() == Money.of(400, "USD")


class TestReturns:
    def test_unsold_goods_go_back_freely(self):
        account = _account()
        assert account.send_back(100, DAY) == 0
        assert account.consignor_inventory().is_zero()

    def test_returning_more_than_held_is_refused(self):
        with pytest.raises(Refused):
            _account().send_back(200, DAY)

    def test_selling_more_than_held_is_refused(self):
        with pytest.raises(Refused) as caught:
            _account().sell(200, Money.of(10, "USD"), DAY)
        assert "physical goods are lost" in str(caught.value)


class TestConstruction:
    def test_a_full_commission_is_refused(self):
        with pytest.raises(Refused):
            ConsignmentAccount("a", "b", "USD", Fraction(1))

    def test_a_wrong_currency_shipment_is_refused(self):
        with pytest.raises(Refused):
            _account().ship(10, Money.of(1, "EUR"), DAY)

    def test_a_zero_shipment_is_refused(self):
        with pytest.raises(Refused):
            _account().ship(0, Money.of(1, "USD"), DAY)

    def test_an_empty_consignment_has_no_inventory(self):
        account = ConsignmentAccount("a", "b", "USD", Fraction(1, 5))
        assert account.consignor_inventory().is_zero()
