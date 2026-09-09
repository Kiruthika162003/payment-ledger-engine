"""Match funding: a finite pot promised against gifts that may exceed it.

A matching campaign promises to double every gift up to a fixed
pot, and the promise is only coherent while the pot lasts. What
happens at the boundary is the whole design question: the gift that
arrives as the pot runs out is matched in part, and every gift
after it is matched not at all, so a campaign that quietly keeps
promising a full match after exhaustion is making a commitment it
cannot fund. This module matches in arrival order, matches the
boundary gift for exactly what remains, and records for every gift
both the match it earned and the match it would have earned, so the
gap is visible rather than inferred. A second mode splits the pot
proportionally across all gifts instead, using largest-remainder so
the allocated amounts sum to the pot exactly, which is fairer to
late donors and worse for anyone who gave early on the strength of
the promise; the module implements both because the choice is a
policy question and not an arithmetic one.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, allocate, round_money


@dataclass(frozen=True)
class Gift:
    id: str
    donor: str
    amount: Money
    received_on: datetime.date

    def __post_init__(self) -> None:
        if not self.amount.is_positive():
            raise Refused("a gift is a positive amount")


@dataclass(frozen=True)
class MatchedGift:
    gift: Gift
    matched: Money
    promised: Money

    def is_full(self) -> bool:
        return self.matched == self.promised

    def is_partial(self) -> bool:
        return self.matched.is_positive() and self.matched < self.promised

    def unmatched(self) -> Money:
        return self.promised - self.matched

    def total_raised(self) -> Money:
        return self.gift.amount + self.matched


@dataclass
class MatchCampaign:
    name: str
    pot: Money
    ratio: Fraction = Fraction(1)
    per_gift_cap: Money | None = None
    gifts: list[Gift] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.pot.is_positive():
            raise Refused("a matching campaign starts with a positive pot")
        if self.ratio <= 0:
            raise Refused(
                "a matching ratio of zero or less matches nothing, so the "
                "campaign has nothing to promise"
            )
        if self.per_gift_cap is not None:
            self.per_gift_cap.same_currency(self.pot)
            if not self.per_gift_cap.is_positive():
                raise Refused("a per-gift cap is positive if it is set at all")

    def receive(self, gift: Gift) -> Gift:
        gift.amount.same_currency(self.pot)
        if any(existing.id == gift.id for existing in self.gifts):
            raise Refused(f"gift {gift.id!r} has already been received")
        self.gifts.append(gift)
        return gift

    def promised_match(self, gift: Gift) -> Money:
        promised = round_money(
            gift.amount.times(self.ratio), self.pot.currency, Rounding.HALF_UP
        )
        if self.per_gift_cap is not None and promised > self.per_gift_cap:
            return self.per_gift_cap
        return promised

    def in_arrival_order(self) -> list[Gift]:
        return sorted(self.gifts, key=lambda gift: (gift.received_on, gift.id))

    def match_in_order(self) -> list[MatchedGift]:
        remaining = self.pot
        results: list[MatchedGift] = []
        for gift in self.in_arrival_order():
            promised = self.promised_match(gift)
            if remaining.is_zero():
                matched = Money.zero(self.pot.currency)
            elif promised > remaining:
                # The boundary gift: matched for exactly what is left, which is
                # the honest amount and not the promised one.
                matched = remaining
            else:
                matched = promised
            remaining = remaining - matched
            results.append(MatchedGift(gift, matched, promised))
        return results

    def match_proportionally(self) -> list[MatchedGift]:
        gifts = self.in_arrival_order()
        if not gifts:
            return []
        weights = [Fraction(gift.amount.units) for gift in gifts]
        total_promised = Money.zero(self.pot.currency)
        for gift in gifts:
            total_promised = total_promised + self.promised_match(gift)
        distributable = self.pot if total_promised > self.pot else total_promised
        shares = allocate(distributable, weights)
        return [
            MatchedGift(gift, share, self.promised_match(gift))
            for gift, share in zip(gifts, shares, strict=True)
        ]

    def pot_used(self, results: list[MatchedGift] | None = None) -> Money:
        rows = self.match_in_order() if results is None else results
        total = Money.zero(self.pot.currency)
        for row in rows:
            total = total + row.matched
        return total

    def pot_remaining(self, results: list[MatchedGift] | None = None) -> Money:
        return self.pot - self.pot_used(results)

    def is_exhausted(self, results: list[MatchedGift] | None = None) -> bool:
        return self.pot_remaining(results).is_zero()

    def exhausting_gift(self) -> Gift | None:
        # The gift that ran the pot out, named so the campaign can tell that
        # donor what actually happened to their money.
        for row in self.match_in_order():
            if row.is_partial():
                return row.gift
        return None

    def unfunded_promise(self, results: list[MatchedGift] | None = None) -> Money:
        rows = self.match_in_order() if results is None else results
        total = Money.zero(self.pot.currency)
        for row in rows:
            total = total + row.unmatched()
        return total

    def total_raised(self, results: list[MatchedGift] | None = None) -> Money:
        rows = self.match_in_order() if results is None else results
        total = Money.zero(self.pot.currency)
        for row in rows:
            total = total + row.total_raised()
        return total

    def gifts_given(self) -> Money:
        total = Money.zero(self.pot.currency)
        for gift in self.gifts:
            total = total + gift.amount
        return total

    def donors(self) -> tuple[str, ...]:
        return tuple(sorted({gift.donor for gift in self.gifts}))

    def raised_by(self, donor: str) -> Money:
        total = Money.zero(self.pot.currency)
        for row in self.match_in_order():
            if row.gift.donor == donor:
                total = total + row.total_raised()
        return total
