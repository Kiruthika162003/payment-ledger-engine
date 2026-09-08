from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.interchange import (
    CardType,
    InterchangeTable,
    Presence,
    Rate,
    RateKey,
    standard_table,
)
from mint.money import Money

DEBIT_PRESENT = RateKey(CardType.DEBIT, Presence.CARD_PRESENT, False)
REWARDS_ONLINE = RateKey(CardType.REWARDS, Presence.CARD_NOT_PRESENT, False)
REWARDS_CROSS = RateKey(CardType.REWARDS, Presence.CARD_NOT_PRESENT, True)


class TestRates:
    def test_a_rewards_card_costs_more_than_a_debit_card(self):
        table = standard_table()
        cheap = table.breakdown(Money.of(100, "USD"), DEBIT_PRESENT)
        dear = table.breakdown(Money.of(100, "USD"), REWARDS_ONLINE)
        assert dear.interchange > cheap.interchange

    def test_cross_border_costs_more_again(self):
        table = standard_table()
        domestic = table.breakdown(Money.of(100, "USD"), REWARDS_ONLINE)
        foreign = table.breakdown(Money.of(100, "USD"), REWARDS_CROSS)
        assert foreign.interchange > domestic.interchange

    def test_an_unpriced_combination_is_refused(self):
        table = standard_table()
        key = RateKey(CardType.CORPORATE, Presence.CARD_PRESENT, True)
        with pytest.raises(Refused) as caught:
            table.breakdown(Money.of(100, "USD"), key)
        assert "misstate the merchant's cost" in str(caught.value)


class TestLayers:
    def test_the_three_layers_are_separated(self):
        breakdown = standard_table().breakdown(Money.of(100, "USD"), DEBIT_PRESENT)
        assert breakdown.interchange.is_positive()
        assert breakdown.assessment.is_positive()
        assert breakdown.processor_margin.is_positive()

    def test_the_total_fee_is_their_sum(self):
        breakdown = standard_table().breakdown(Money.of(100, "USD"), DEBIT_PRESENT)
        assert breakdown.total_fee() == (
            breakdown.interchange + breakdown.assessment + breakdown.processor_margin
        )

    def test_the_merchant_nets_the_rest(self):
        breakdown = standard_table().breakdown(Money.of(100, "USD"), DEBIT_PRESENT)
        assert breakdown.reconciles()
        assert breakdown.net_to_merchant() < Money.of(100, "USD")

    def test_only_the_processor_share_is_negotiable(self):
        breakdown = standard_table().breakdown(Money.of(100, "USD"), REWARDS_CROSS)
        share = breakdown.negotiable_share()
        assert share is not None
        assert share < Fraction(1, 2)


class TestConstruction:
    def test_a_rate_of_one_is_refused(self):
        with pytest.raises(Refused):
            Rate(Fraction(1), Money.zero("USD"))

    def test_a_negative_fixed_component_is_refused(self):
        with pytest.raises(Refused):
            Rate(Fraction(1, 100), Money.of("-0.10", "USD"))

    def test_a_wrong_currency_rate_is_refused(self):
        table = standard_table()
        with pytest.raises(Refused):
            table.set_rate(DEBIT_PRESENT, Rate(Fraction(1, 100), Money.of(1, "EUR")))

    def test_a_wrong_currency_transaction_is_refused(self):
        with pytest.raises(Refused):
            standard_table().breakdown(Money.of(100, "EUR"), DEBIT_PRESENT)

    def test_a_nonpositive_transaction_is_refused(self):
        with pytest.raises(Refused):
            standard_table().breakdown(Money.zero("USD"), DEBIT_PRESENT)

    def test_a_custom_table_can_be_built(self):
        table = InterchangeTable(
            currency="USD",
            assessment_rate=Fraction(1, 1000),
            processor_percent=Fraction(2, 1000),
            processor_fixed=Money.of("0.05", "USD"),
        )
        table.set_rate(DEBIT_PRESENT, Rate(Fraction(4, 1000), Money.of("0.05", "USD")))
        assert table.breakdown(Money.of(100, "USD"), DEBIT_PRESENT).reconciles()
