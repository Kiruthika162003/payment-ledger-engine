from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.franchise import FranchiseAgreement, FranchiseNetwork
from mint.money import Money

SIGNED = datetime.date(2026, 1, 1)


def _agreement(**kwargs) -> FranchiseAgreement:
    base = {
        "id": "F-1",
        "franchisee": "Store 12",
        "initial_fee": Money.of(30000, "USD"),
        "royalty_rate": Fraction(6, 100),
        "ad_fund_rate": Fraction(2, 100),
        "signed_on": SIGNED,
        "obligations_total": 3,
    }
    base.update(kwargs)
    return FranchiseAgreement(**base)


class TestInitialFee:
    def test_nothing_is_recognized_on_signature(self):
        agreement = _agreement()
        assert agreement.initial_fee_recognized.is_zero()
        assert agreement.deferred_initial_fee() == Money.of(30000, "USD")

    def test_it_recognizes_as_obligations_are_met(self):
        agreement = _agreement()
        assert agreement.meet_obligation() == Money.of(10000, "USD")
        assert agreement.deferred_initial_fee() == Money.of(20000, "USD")

    def test_the_last_obligation_clears_the_balance(self):
        agreement = _agreement()
        for _ in range(3):
            agreement.meet_obligation()
        assert agreement.deferred_initial_fee().is_zero()
        assert agreement.is_fully_opened()

    def test_an_awkward_fee_still_clears(self):
        agreement = _agreement(initial_fee=Money.of("10000.01", "USD"))
        for _ in range(3):
            agreement.meet_obligation()
        assert agreement.deferred_initial_fee().is_zero()

    def test_meeting_more_obligations_than_exist_is_refused(self):
        agreement = _agreement(obligations_total=1)
        agreement.meet_obligation()
        with pytest.raises(Refused):
            agreement.meet_obligation()


class TestRoyalties:
    def test_sales_generate_a_royalty_and_a_contribution(self):
        agreement = _agreement()
        royalty, contribution = agreement.report_sales(Money.of(100000, "USD"))
        assert royalty == Money.of(6000, "USD")
        assert contribution == Money.of(2000, "USD")

    def test_royalties_accumulate_into_revenue(self):
        agreement = _agreement()
        agreement.report_sales(Money.of(100000, "USD"))
        agreement.report_sales(Money.of(50000, "USD"))
        assert agreement.royalties_earned == Money.of(9000, "USD")

    def test_a_nonpositive_sale_is_refused(self):
        with pytest.raises(Refused):
            _agreement().report_sales(Money.zero("USD"))


class TestAdvertisingFund:
    def test_the_fund_is_not_revenue(self):
        agreement = _agreement()
        agreement.report_sales(Money.of(100000, "USD"))
        assert not agreement.fund_is_revenue()
        assert agreement.fund_balance() == Money.of(2000, "USD")

    def test_franchisor_revenue_excludes_the_fund(self):
        agreement = _agreement()
        agreement.meet_obligation()
        agreement.report_sales(Money.of(100000, "USD"))
        assert agreement.franchisor_revenue() == Money.of(16000, "USD")

    def test_spending_the_fund_reduces_the_balance(self):
        agreement = _agreement()
        agreement.report_sales(Money.of(100000, "USD"))
        agreement.spend_fund(Money.of(800, "USD"), "regional campaign")
        assert agreement.fund_balance() == Money.of(1200, "USD")

    def test_overspending_the_fund_is_refused(self):
        agreement = _agreement()
        agreement.report_sales(Money.of(100000, "USD"))
        with pytest.raises(Refused):
            agreement.spend_fund(Money.of(5000, "USD"), "big campaign")

    def test_fund_spending_records_its_purpose(self):
        agreement = _agreement()
        agreement.report_sales(Money.of(100000, "USD"))
        with pytest.raises(Refused):
            agreement.spend_fund(Money.of(100, "USD"), "  ")


class TestNetwork:
    def _network(self) -> FranchiseNetwork:
        network = FranchiseNetwork("USD")
        network.add(_agreement())
        network.add(_agreement(id="F-2", franchisee="Store 13"))
        return network

    def test_the_network_totals_revenue_and_the_fund_apart(self):
        network = self._network()
        for agreement in network.agreements:
            agreement.report_sales(Money.of(100000, "USD"))
        assert network.total_revenue() == Money.of(12000, "USD")
        assert network.total_fund_held() == Money.of(4000, "USD")

    def test_deferred_fees_are_totalled(self):
        assert self._network().total_deferred() == Money.of(60000, "USD")

    def test_a_duplicate_agreement_is_refused(self):
        network = self._network()
        with pytest.raises(Refused):
            network.add(_agreement())

    def test_a_wrong_currency_agreement_is_refused(self):
        network = self._network()
        with pytest.raises(Refused):
            network.add(_agreement(id="F-9", initial_fee=Money.of(100, "EUR")))

    def test_a_rate_of_one_is_refused(self):
        with pytest.raises(Refused):
            _agreement(royalty_rate=Fraction(1))
