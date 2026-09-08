from __future__ import annotations

import pytest

from mint.errors import CurrencyMismatch, Refused
from mint.money import Money
from mint.settlement import ItemKind, SettlementItem, settle


def _item(kind, amount):
    return SettlementItem(kind, Money.of(amount, "USD"))


class TestSettle:
    def test_net_is_charges_less_refunds_less_fees(self):
        batch = settle(
            [
                _item(ItemKind.CHARGE, 100),
                _item(ItemKind.CHARGE, 50),
                _item(ItemKind.REFUND, 20),
                _item(ItemKind.FEE, 5),
            ],
            "USD",
        )
        assert batch.gross_charges == Money.of(150, "USD")
        assert batch.gross_refunds == Money.of(20, "USD")
        assert batch.fees == Money.of(5, "USD")
        assert batch.net == Money.of(125, "USD")

    def test_a_heavy_refund_day_owes_the_processor(self):
        batch = settle(
            [_item(ItemKind.CHARGE, 10), _item(ItemKind.REFUND, 40)],
            "USD",
        )
        assert batch.owes_processor()
        assert batch.net == Money.of("-30.00", "USD")

    def test_the_item_count_is_reported(self):
        batch = settle([_item(ItemKind.CHARGE, 10)], "USD")
        assert batch.item_count == 1


class TestRefusals:
    def test_a_mixed_currency_batch_is_refused(self):
        with pytest.raises(CurrencyMismatch):
            settle(
                [
                    SettlementItem(ItemKind.CHARGE, Money.of(10, "USD")),
                    SettlementItem(ItemKind.CHARGE, Money.of(10, "EUR")),
                ],
                "USD",
            )

    def test_an_empty_batch_is_refused(self):
        with pytest.raises(Refused):
            settle([], "USD")

    def test_a_nonpositive_item_is_refused(self):
        with pytest.raises(Refused):
            settle([SettlementItem(ItemKind.CHARGE, Money.zero("USD"))], "USD")
