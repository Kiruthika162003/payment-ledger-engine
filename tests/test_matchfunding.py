from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.matchfunding import Gift, MatchCampaign
from mint.money import Money

DAY = datetime.date(2026, 5, 1)


def _gift(gift_id: str, donor: str, amount: int, day: int = 1) -> Gift:
    return Gift(gift_id, donor, Money.of(amount, "USD"), datetime.date(2026, 5, day))


def _campaign(**kwargs) -> MatchCampaign:
    base = {"name": "spring appeal", "pot": Money.of(1000, "USD")}
    base.update(kwargs)
    campaign = MatchCampaign(**base)
    campaign.receive(_gift("G-1", "alice", 400, day=1))
    campaign.receive(_gift("G-2", "bob", 400, day=2))
    campaign.receive(_gift("G-3", "carol", 400, day=3))
    return campaign


class TestArrivalOrder:
    def test_early_gifts_are_matched_in_full(self):
        rows = _campaign().match_in_order()
        assert rows[0].is_full()
        assert rows[1].is_full()

    def test_the_boundary_gift_is_matched_in_part(self):
        rows = _campaign().match_in_order()
        assert rows[2].is_partial()
        assert rows[2].matched == Money.of(200, "USD")

    def test_the_pot_is_used_exactly(self):
        campaign = _campaign()
        assert campaign.pot_used() == campaign.pot
        assert campaign.is_exhausted()

    def test_a_gift_after_exhaustion_is_matched_by_nothing(self):
        campaign = _campaign()
        campaign.receive(_gift("G-4", "dave", 400, day=4))
        rows = campaign.match_in_order()
        assert rows[3].matched.is_zero()
        assert not rows[3].is_partial()

    def test_the_exhausting_gift_is_named(self):
        exhausting = _campaign().exhausting_gift()
        assert exhausting is not None
        assert exhausting.id == "G-3"

    def test_an_unexhausted_pot_names_nobody(self):
        campaign = MatchCampaign("small", Money.of(10000, "USD"))
        campaign.receive(_gift("G-1", "alice", 100))
        assert campaign.exhausting_gift() is None


class TestPromiseGap:
    def test_the_unfunded_promise_is_visible(self):
        campaign = _campaign()
        campaign.receive(_gift("G-4", "dave", 400, day=4))
        assert campaign.unfunded_promise() == Money.of(600, "USD")

    def test_a_fully_funded_campaign_promises_nothing_it_cannot_pay(self):
        campaign = MatchCampaign("roomy", Money.of(10000, "USD"))
        campaign.receive(_gift("G-1", "alice", 100))
        assert campaign.unfunded_promise().is_zero()

    def test_the_gap_on_a_partial_gift_is_the_difference(self):
        rows = _campaign().match_in_order()
        assert rows[2].unmatched() == Money.of(200, "USD")


class TestRatioAndCap:
    def test_a_half_ratio_matches_half(self):
        campaign = _campaign(pot=Money.of(10000, "USD"), ratio=Fraction(1, 2))
        assert campaign.match_in_order()[0].matched == Money.of(200, "USD")

    def test_a_double_ratio_matches_twice(self):
        campaign = _campaign(pot=Money.of(10000, "USD"), ratio=Fraction(2))
        assert campaign.match_in_order()[0].matched == Money.of(800, "USD")

    def test_a_per_gift_cap_limits_a_large_donor(self):
        campaign = _campaign(
            pot=Money.of(10000, "USD"), per_gift_cap=Money.of(100, "USD")
        )
        assert campaign.match_in_order()[0].matched == Money.of(100, "USD")
        assert campaign.pot_used() == Money.of(300, "USD")

    def test_a_zero_ratio_is_refused(self):
        with pytest.raises(Refused) as caught:
            _campaign(ratio=Fraction(0))
        assert "nothing to promise" in str(caught.value)

    def test_a_nonpositive_cap_is_refused(self):
        with pytest.raises(Refused):
            _campaign(per_gift_cap=Money.zero("USD"))


class TestProportionalMode:
    def test_the_pot_is_split_across_every_gift(self):
        rows = _campaign().match_proportionally()
        assert all(row.matched.is_positive() for row in rows)

    def test_the_shares_sum_to_the_pot_exactly(self):
        campaign = _campaign()
        rows = campaign.match_proportionally()
        assert campaign.pot_used(rows) == campaign.pot

    def test_an_uneven_split_still_conserves_the_pot(self):
        # Guessed three one-dollar gifts against a ten-dollar pot would split
        # the pot; measured three dollars, because the promise is only three
        # dollars and the pot is not the binding constraint. The gifts have to
        # overpromise before the split has anything to divide.
        campaign = MatchCampaign("odd", Money.of("10.00", "USD"))
        campaign.receive(_gift("G-1", "alice", 5, day=1))
        campaign.receive(_gift("G-2", "bob", 5, day=2))
        campaign.receive(_gift("G-3", "carol", 5, day=3))
        rows = campaign.match_proportionally()
        assert campaign.pot_used(rows) == Money.of("10.00", "USD")
        # A thousand minor units across three gifts: largest remainder gives
        # the extra unit to the first, not a third of a cent to everyone.
        assert [row.matched.units for row in rows] == [334, 333, 333]

    def test_a_promise_below_the_pot_is_not_inflated_to_fill_it(self):
        campaign = MatchCampaign("roomy", Money.of("10.00", "USD"))
        campaign.receive(_gift("G-1", "alice", 1, day=1))
        campaign.receive(_gift("G-2", "bob", 1, day=2))
        rows = campaign.match_proportionally()
        assert campaign.pot_used(rows) == Money.of("2.00", "USD")

    def test_a_pot_larger_than_the_promise_is_not_overspent(self):
        campaign = _campaign(pot=Money.of(10000, "USD"))
        rows = campaign.match_proportionally()
        assert campaign.pot_used(rows) == Money.of(1200, "USD")

    def test_an_empty_campaign_matches_nothing(self):
        campaign = MatchCampaign("quiet", Money.of(100, "USD"))
        assert campaign.match_proportionally() == []


class TestTotals:
    def test_the_total_raised_is_gifts_plus_match(self):
        campaign = _campaign()
        assert campaign.total_raised() == Money.of(2200, "USD")

    def test_the_gifts_alone_are_reported(self):
        assert _campaign().gifts_given() == Money.of(1200, "USD")

    def test_a_donor_sees_what_their_gift_raised(self):
        campaign = _campaign()
        assert campaign.raised_by("alice") == Money.of(800, "USD")
        assert campaign.raised_by("carol") == Money.of(600, "USD")

    def test_the_donors_are_listed_in_order(self):
        assert _campaign().donors() == ("alice", "bob", "carol")

    def test_the_remaining_pot_shrinks_as_gifts_land(self):
        campaign = MatchCampaign("roomy", Money.of(10000, "USD"))
        campaign.receive(_gift("G-1", "alice", 100))
        assert campaign.pot_remaining() == Money.of(9900, "USD")


class TestConstruction:
    def test_a_nonpositive_pot_is_refused(self):
        with pytest.raises(Refused):
            MatchCampaign("empty", Money.zero("USD"))

    def test_a_duplicate_gift_is_refused(self):
        campaign = _campaign()
        with pytest.raises(Refused):
            campaign.receive(_gift("G-1", "alice", 400))

    def test_a_wrong_currency_gift_is_refused(self):
        campaign = _campaign()
        with pytest.raises(Refused):
            campaign.receive(Gift("G-9", "eve", Money.of(10, "EUR"), DAY))

    def test_a_nonpositive_gift_is_refused(self):
        with pytest.raises(Refused):
            Gift("G-0", "nobody", Money.zero("USD"), DAY)
