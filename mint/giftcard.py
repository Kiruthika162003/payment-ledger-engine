"""Gift cards: a fixed load spent down in pieces, with an expiry that bites.

A gift card is stored value with two twists a plain wallet does not
have: it is loaded once rather than topped up freely, and it
expires. Both twists are places money goes missing if the code is
loose. The single load fixes the card's ceiling, and every
redemption draws it down, refusing to redeem more than remains so a
card cannot be spent twice. Expiry is the subtle one: a redemption
dated after the expiry is refused because the value is gone, and
the remaining balance on an expired card is reported as forfeited
rather than spendable, which is what lets the issuer recognize the
breakage as income at the right moment instead of carrying a
liability that can no longer be claimed. The balance is folded from
the load and the redemptions so it can always be reconstructed, and
the card reports whether it is exhausted, expired, or still live, a
distinction the issuer needs because an exhausted card and an
expired one leave the books in different places even though both
have nothing left to spend.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.errors import InsufficientFunds, Refused
from mint.money import Money


@dataclass(frozen=True)
class Redemption:
    date: datetime.date
    amount: Money


@dataclass
class GiftCard:
    code: str
    loaded: Money
    issued: datetime.date
    expires: datetime.date | None = None
    redemptions: list[Redemption] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.loaded.is_positive():
            raise Refused("a gift card is loaded with a positive amount")

    def redeemed_total(self) -> Money:
        total = Money.zero(self.loaded.currency)
        for redemption in self.redemptions:
            total = total + redemption.amount
        return total

    def balance(self) -> Money:
        return self.loaded - self.redeemed_total()

    def is_expired(self, as_of: datetime.date) -> bool:
        return self.expires is not None and as_of > self.expires

    def redeem(self, amount: Money, on: datetime.date) -> Money:
        amount.same_currency(self.loaded)
        if not amount.is_positive():
            raise Refused("a redemption draws a positive amount")
        if self.is_expired(on):
            raise Refused(
                f"gift card {self.code!r} expired on {self.expires.isoformat()}; "
                "its value is forfeited"
            )
        if amount > self.balance():
            raise InsufficientFunds(
                f"a redemption of {amount.format()} exceeds the "
                f"{self.balance().format()} left on card {self.code!r}"
            )
        self.redemptions.append(Redemption(on, amount))
        return self.balance()

    def forfeited(self, as_of: datetime.date) -> Money:
        if self.is_expired(as_of):
            return self.balance()
        return Money.zero(self.loaded.currency)

    def is_live(self, as_of: datetime.date) -> bool:
        return not self.is_expired(as_of) and self.balance().is_positive()
