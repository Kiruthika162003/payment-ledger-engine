from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.warranty import ClaimHistory, WarrantyProvision


def _history(**kwargs) -> ClaimHistory:
    base = {
        "units_sold": 1000,
        "claims_made": 50,
        "total_claim_cost": Money.of(20000, "USD"),
    }
    base.update(kwargs)
    return ClaimHistory(**base)


def _provision() -> WarrantyProvision:
    return WarrantyProvision(currency="USD", history=_history())


class TestHistory:
    def test_the_claim_rate_comes_from_the_history(self):
        assert _history().claim_rate() == Fraction(1, 20)

    def test_the_average_claim_cost(self):
        assert _history().average_claim_cost() == Money.of(400, "USD")

    def test_cost_per_unit_sold_blends_both(self):
        assert _history().cost_per_unit_sold() == Fraction(2000000, 1000)

    def test_a_history_with_no_claims_averages_nothing(self):
        history = _history(claims_made=0, total_claim_cost=Money.zero("USD"))
        assert history.average_claim_cost().is_zero()

    def test_more_claims_than_units_is_refused(self):
        with pytest.raises(Refused) as caught:
            _history(units_sold=10, claims_made=20)
        assert "wrong population" in str(caught.value)


class TestProvisioning:
    def test_selling_creates_an_obligation(self):
        provision = _provision()
        provision.sell(500)
        # 20000 over 1000 units is 20.00 a unit, so 500 units needs 10000.
        assert provision.required_provision() == Money.of(10000, "USD")

    def test_the_movement_is_the_increment(self):
        provision = _provision()
        provision.sell(500)
        assert provision.post_provision() == Money.of(10000, "USD")
        provision.sell(100)
        assert provision.movement() == Money.of(2000, "USD")

    def test_posting_twice_without_sales_provides_nothing(self):
        provision = _provision()
        provision.sell(500)
        provision.post_provision()
        assert provision.post_provision().is_zero()


class TestUtilization:
    def test_claims_consume_the_provision(self):
        provision = _provision()
        provision.sell(500)
        provision.post_provision()
        provision.pay_claim(Money.of(4000, "USD"))
        assert provision.remaining() == Money.of(6000, "USD")
        assert provision.utilization() == Fraction(2, 5)

    def test_an_over_provision_is_named(self):
        provision = _provision()
        provision.sell(500)
        provision.post_provision()
        provision.pay_claim(Money.of(1000, "USD"))
        assert "over-provided" in provision.verdict()

    def test_an_under_provision_is_named(self):
        provision = _provision()
        provision.sell(500)
        provision.post_provision()
        provision.pay_claim(Money.of(15000, "USD"))
        assert provision.is_under_provided()
        assert "given back" in provision.verdict()

    def test_a_tracking_provision_is_named(self):
        provision = _provision()
        provision.sell(500)
        provision.post_provision()
        provision.pay_claim(Money.of(8000, "USD"))
        assert "tracking the claims" in provision.verdict()

    def test_nothing_provided_yet(self):
        assert _provision().utilization() is None
        assert "nothing provided yet" in _provision().verdict()


class TestRefusals:
    def test_a_nonpositive_claim_is_refused(self):
        with pytest.raises(Refused):
            _provision().pay_claim(Money.zero("USD"))

    def test_a_zero_sale_is_refused(self):
        with pytest.raises(Refused):
            _provision().sell(0)

    def test_a_currency_mismatch_is_refused(self):
        with pytest.raises(Refused):
            WarrantyProvision(
                currency="EUR",
                history=_history(),
            )
