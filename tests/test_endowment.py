from __future__ import annotations

from fractions import Fraction

import pytest

from mint.endowment import Endowment
from mint.errors import Refused
from mint.money import Money


def _endowment(**kwargs) -> Endowment:
    base = {
        "id": "E-1",
        "corpus": Money.of(1000000, "USD"),
        "market_value": Money.of(1200000, "USD"),
        "spending_rate": Fraction(4, 100),
    }
    base.update(kwargs)
    return Endowment(**base)


class TestSpendingPolicy:
    def test_the_spend_comes_off_the_average(self):
        endowment = _endowment()
        assert endowment.permitted_spend() == Money.of(48000, "USD")

    def test_the_average_smooths_a_bad_year(self):
        endowment = _endowment()
        endowment.record_value(Money.of(1200000, "USD"))
        endowment.record_value(Money.of(600000, "USD"))
        # The average of the three, not the latest value alone.
        assert endowment.average_value() == Money.of(1000000, "USD")
        assert endowment.permitted_spend() == Money.of(40000, "USD")

    def test_the_window_is_limited_to_the_averaging_years(self):
        endowment = _endowment(averaging_years=2)
        endowment.record_value(Money.of(2000000, "USD"))
        endowment.record_value(Money.of(2000000, "USD"))
        assert endowment.average_value() == Money.of(2000000, "USD")

    def test_a_negative_value_is_refused(self):
        with pytest.raises(Refused):
            _endowment().record_value(Money.of("-1.00", "USD"))


class TestUnderwater:
    def test_a_healthy_endowment_preserves_capital(self):
        endowment = _endowment()
        assert not endowment.is_underwater()
        assert endowment.preserves_capital()
        assert endowment.headroom() == Money.of(200000, "USD")

    def test_a_fallen_portfolio_is_underwater(self):
        endowment = _endowment(market_value=Money.of(800000, "USD"))
        assert endowment.is_underwater()
        assert endowment.shortfall() == Money.of(200000, "USD")

    def test_a_healthy_endowment_has_no_shortfall(self):
        assert _endowment().shortfall().is_zero()


class TestDistribution:
    def test_a_permitted_distribution_reduces_the_value(self):
        endowment = _endowment()
        endowment.distribute(Money.of(40000, "USD"))
        assert endowment.market_value == Money.of(1160000, "USD")
        assert endowment.distributed == Money.of(40000, "USD")

    def test_spending_beyond_the_policy_is_refused(self):
        with pytest.raises(Refused) as caught:
            _endowment().distribute(Money.of(100000, "USD"))
        assert "spending policy allows" in str(caught.value)

    def test_spending_into_the_corpus_is_refused_by_default(self):
        endowment = _endowment(market_value=Money.of(1010000, "USD"))
        with pytest.raises(Refused) as caught:
            endowment.distribute(Money.of(40000, "USD"))
        assert "how a permanent fund is consumed" in str(caught.value)

    def test_invasion_is_possible_when_stated_explicitly(self):
        endowment = _endowment(market_value=Money.of(1010000, "USD"))
        endowment.distribute(Money.of(40000, "USD"), allow_invasion=True)
        assert endowment.is_underwater()

    def test_a_nonpositive_distribution_is_refused(self):
        with pytest.raises(Refused):
            _endowment().distribute(Money.zero("USD"))


class TestReturn:
    def test_total_return_counts_growth_and_distributions(self):
        endowment = _endowment()
        endowment.distribute(Money.of(40000, "USD"))
        assert endowment.total_return() == Money.of(200000, "USD")

    def test_a_flat_endowment_has_no_return(self):
        endowment = _endowment(market_value=Money.of(1000000, "USD"))
        assert endowment.total_return().is_zero()


class TestConstruction:
    def test_a_nonpositive_corpus_is_refused(self):
        with pytest.raises(Refused):
            _endowment(corpus=Money.zero("USD"))

    def test_a_spending_rate_of_one_is_refused(self):
        with pytest.raises(Refused):
            _endowment(spending_rate=Fraction(1))

    def test_a_zero_averaging_window_is_refused(self):
        with pytest.raises(Refused):
            _endowment(averaging_years=0)
