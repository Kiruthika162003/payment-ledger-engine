from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.sharecapital import Issue, ShareCapital

DAY = datetime.date(2026, 1, 1)


def _capital() -> ShareCapital:
    return ShareCapital(currency="USD", par_value=Money.of(1, "USD"))


class TestIssuing:
    def test_an_issue_splits_par_from_premium(self):
        capital = _capital()
        issue = capital.issue(1000, Money.of(5, "USD"), DAY)
        assert issue.nominal_total() == Money.of(1000, "USD")
        assert issue.premium_total() == Money.of(4000, "USD")
        assert issue.proceeds() == Money.of(5000, "USD")

    def test_the_register_totals_both(self):
        capital = _capital()
        capital.issue(1000, Money.of(5, "USD"), DAY)
        assert capital.share_capital() == Money.of(1000, "USD")
        assert capital.share_premium() == Money.of(4000, "USD")

    def test_issuing_at_par_creates_no_premium(self):
        capital = _capital()
        capital.issue(1000, Money.of(1, "USD"), DAY)
        assert capital.share_premium().is_zero()

    def test_issuing_below_par_is_refused(self):
        capital = _capital()
        with pytest.raises(Refused) as caught:
            capital.issue(1000, Money.of("0.50", "USD"), DAY)
        assert "never contributed" in str(caught.value)

    def test_a_zero_share_issue_is_refused(self):
        with pytest.raises(Refused):
            Issue(DAY, 0, Money.of(5, "USD"), Money.of(1, "USD"))


class TestDistributable:
    def test_capital_and_premium_are_not_distributable(self):
        capital = _capital()
        capital.issue(1000, Money.of(5, "USD"), DAY)
        assert capital.total_equity() == Money.of(5000, "USD")
        assert capital.distributable_reserves().is_zero()

    def test_only_retained_earnings_are_distributable(self):
        capital = _capital()
        capital.issue(1000, Money.of(5, "USD"), DAY)
        capital.earn(Money.of(800, "USD"))
        assert capital.distributable_reserves() == Money.of(800, "USD")

    def test_a_company_with_capital_and_no_profit_cannot_distribute(self):
        capital = _capital()
        capital.issue(10000, Money.of(10, "USD"), DAY)
        assert not capital.can_distribute(Money.of(1, "USD"))

    def test_losses_do_not_make_reserves_negative_for_this_test(self):
        capital = _capital()
        capital.earn(Money.of("-500.00", "USD"))
        assert capital.distributable_reserves().is_zero()


class TestBuyback:
    def test_a_buyback_reduces_shares_and_reserves(self):
        capital = _capital()
        capital.issue(1000, Money.of(5, "USD"), DAY)
        capital.earn(Money.of(2000, "USD"))
        cost = capital.buy_back(100, Money.of(6, "USD"), DAY)
        assert cost == Money.of(600, "USD")
        assert capital.shares_issued() == 900
        assert capital.distributable_reserves() == Money.of(1400, "USD")

    def test_a_buyback_beyond_reserves_is_refused(self):
        capital = _capital()
        capital.issue(1000, Money.of(5, "USD"), DAY)
        capital.earn(Money.of(100, "USD"))
        with pytest.raises(Refused) as caught:
            capital.buy_back(100, Money.of(6, "USD"), DAY)
        assert "ahead of creditors" in str(caught.value)

    def test_buying_back_more_than_issued_is_refused(self):
        capital = _capital()
        capital.issue(100, Money.of(5, "USD"), DAY)
        capital.earn(Money.of(100000, "USD"))
        with pytest.raises(Refused):
            capital.buy_back(500, Money.of(5, "USD"), DAY)

    def test_a_zero_share_buyback_is_refused(self):
        capital = _capital()
        capital.issue(100, Money.of(5, "USD"), DAY)
        with pytest.raises(Refused):
            capital.buy_back(0, Money.of(5, "USD"), DAY)


class TestConstruction:
    def test_a_nonpositive_par_value_is_refused(self):
        with pytest.raises(Refused):
            ShareCapital(currency="USD", par_value=Money.zero("USD"))

    def test_a_mismatched_par_currency_is_refused(self):
        with pytest.raises(Refused):
            ShareCapital(currency="USD", par_value=Money.of(1, "EUR"))

    def test_a_wrong_currency_issue_is_refused(self):
        with pytest.raises(Refused):
            _capital().issue(100, Money.of(5, "EUR"), DAY)

    def test_the_total_raised_is_tracked(self):
        capital = _capital()
        capital.issue(1000, Money.of(5, "USD"), DAY)
        capital.issue(500, Money.of(8, "USD"), DAY)
        assert capital.total_raised() == Money.of(9000, "USD")
