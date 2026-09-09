"""Unit pricing: turning a pooled fund into a per-unit price that new money buys at.

A pooled fund holds one basket of assets on behalf of many owners,
and the only honest way to let someone join or leave is to price a
unit at the fund's net assets divided by the units already issued.
The arithmetic looks trivial and the danger hides in the rounding:
if the unit price is rounded and then multiplied back by the units
issued, the value handed to the new investor does not equal the
cash they paid, and the difference is quietly taken from or given
to everyone already in the fund. This module keeps the price as an
exact Fraction and rounds only when reporting it, computes units
from the unrounded price, and refuses to price a fund with no units
or no assets rather than dividing by zero and calling the result a
price. It also carries the dilution levy, which is the deliberate
answer to a real transfer: buying assets to accommodate a new
investor costs money, and charging that cost to the fund charges it
to the wrong people.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


@dataclass(frozen=True)
class UnitHolding:
    holder: str
    units: Fraction

    def __post_init__(self) -> None:
        if self.units <= 0:
            raise Refused("a holding covers a positive number of units")


@dataclass(frozen=True)
class Dealing:
    holder: str
    kind: str
    units: Fraction
    consideration: Money
    levy: Money

    def is_issue(self) -> bool:
        return self.kind == "issue"

    def net_consideration(self) -> Money:
        # What actually reaches the fund: the levy stays with the fund on an
        # issue and is withheld from the payout on a redemption.
        if self.is_issue():
            return self.consideration - self.levy
        return self.consideration - self.levy


@dataclass
class UnitFund:
    name: str
    currency: str
    net_assets: Money
    units_issued: Fraction
    dilution_levy_rate: Fraction = Fraction(0)
    price_places: int = 4
    holdings: dict[str, Fraction] = field(default_factory=dict)
    dealings: list[Dealing] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.net_assets.currency != self.currency:
            raise Refused(
                f"fund {self.name!r} is denominated in {self.currency} but holds "
                f"net assets in {self.net_assets.currency}"
            )
        if self.units_issued < 0:
            raise Refused("a fund cannot have issued a negative number of units")
        if self.dilution_levy_rate < 0:
            raise Refused("a dilution levy rate is not negative")
        if self.price_places < 0:
            raise Refused("a price is quoted to a non-negative number of places")

    def exact_price(self) -> Fraction:
        if self.units_issued <= 0:
            raise Refused(
                f"fund {self.name!r} has no units issued, so there is nothing to "
                "divide the net assets by; seed the fund before pricing it"
            )
        if not self.net_assets.is_positive():
            raise Refused(
                f"fund {self.name!r} has net assets of {self.net_assets.format()}, "
                "which is not a price anyone can deal at"
            )
        return Fraction(self.net_assets.units, self.units_issued)

    def quoted_price(self) -> Fraction:
        # Rounded for publication only. Dealing uses exact_price, because
        # rounding first and multiplying second moves money between holders.
        scale = 10**self.price_places
        exact = self.exact_price()
        return Fraction(round(exact * scale), scale)

    def price_as_money(self) -> Money:
        return round_money(self.exact_price(), self.currency, Rounding.HALF_EVEN)

    def levy_on(self, amount: Money) -> Money:
        if self.dilution_levy_rate == 0:
            return Money.zero(self.currency)
        return round_money(
            amount.times(self.dilution_levy_rate), self.currency, Rounding.HALF_UP
        )

    def units_for(self, amount: Money) -> Fraction:
        amount.same_currency(self.net_assets)
        if not amount.is_positive():
            raise Refused("an investment buys units only if it is positive")
        invested = amount - self.levy_on(amount)
        return Fraction(invested.units) / self.exact_price()

    def issue(self, holder: str, amount: Money) -> Dealing:
        units = self.units_for(amount)
        levy = self.levy_on(amount)
        self.net_assets = self.net_assets + amount
        self.units_issued += units
        self.holdings[holder] = self.holdings.get(holder, Fraction(0)) + units
        dealing = Dealing(holder, "issue", units, amount, levy)
        self.dealings.append(dealing)
        return dealing

    def redeem(self, holder: str, units: Fraction) -> Dealing:
        held = self.holdings.get(holder, Fraction(0))
        if units <= 0:
            raise Refused("a redemption covers a positive number of units")
        if units > held:
            raise Refused(
                f"{holder!r} holds {held} units and cannot redeem {units}; "
                "a fund does not lend units to its own investors"
            )
        gross = round_money(
            self.exact_price() * units, self.currency, Rounding.HALF_EVEN
        )
        levy = self.levy_on(gross)
        self.net_assets = self.net_assets - gross
        self.units_issued -= units
        remaining = held - units
        if remaining == 0:
            del self.holdings[holder]
        else:
            self.holdings[holder] = remaining
        dealing = Dealing(holder, "redemption", units, gross, levy)
        self.dealings.append(dealing)
        return dealing

    def value_of(self, holder: str) -> Money:
        units = self.holdings.get(holder, Fraction(0))
        if units == 0:
            return Money.zero(self.currency)
        return round_money(
            self.exact_price() * units, self.currency, Rounding.HALF_EVEN
        )

    def revalue(self, net_assets: Money) -> Fraction:
        net_assets.same_currency(self.net_assets)
        self.net_assets = net_assets
        return self.exact_price()

    def holders(self) -> tuple[str, ...]:
        return tuple(sorted(self.holdings))

    def units_held(self) -> Fraction:
        total = Fraction(0)
        for units in self.holdings.values():
            total += units
        return total

    def unattributed_units(self) -> Fraction:
        # Units issued but not booked to a holder: the seed units of a fund
        # started by its manager sit here until someone claims them.
        return self.units_issued - self.units_held()

    def rounding_drift(self) -> Money:
        # What the published price would misstate the fund by if anyone dealt
        # at it. Reported rather than hidden.
        quoted = self.quoted_price()
        at_quoted = round_money(
            quoted * self.units_issued, self.currency, Rounding.HALF_EVEN
        )
        return at_quoted - self.net_assets
