"""Revaluation: restating a foreign balance at today's rate, booking the swing.

A balance held in a foreign currency was carried on the books at
the rate in force when it was booked, but rates move, and at
period end the balance is worth a different amount in the home
currency than the carrying value says. Revaluation is the entry
that restates it: value the foreign balance at the current rate,
compare to the carrying value, and the difference is an unrealized
gain or loss that has not been settled but is real enough to
report. This module computes that swing exactly, converting the
foreign balance to the base currency at the current rate and
subtracting the carrying value, and it is careful about sign so a
foreign asset that strengthened books a gain while a foreign
liability that strengthened books a loss, because owing more in
home-currency terms is worse, not better. The gain or loss is
unrealized, so the convention is that it reverses next period
before the fresh revaluation, and the module reports the figure and
its direction plainly so the caller can post the reversing pair
without re-deriving which way the rate moved.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.conversion import convert_at
from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding


@dataclass(frozen=True)
class Revaluation:
    foreign: Money
    carrying: Money
    revalued: Money
    gain_loss: Money

    def is_gain(self) -> bool:
        return self.gain_loss.is_positive()

    def is_loss(self) -> bool:
        return self.gain_loss.is_negative()


def revalue(
    foreign: Money,
    carrying: Money,
    rate_to_base: Fraction,
    is_liability: bool = False,
    mode: Rounding = Rounding.HALF_EVEN,
) -> Revaluation:
    if foreign.currency == carrying.currency:
        raise Refused(
            "revaluation restates a foreign balance in the base currency; the "
            "two currencies given are the same"
        )
    revalued = convert_at(foreign, carrying.currency, rate_to_base, mode)
    swing = revalued - carrying
    if is_liability:
        swing = -swing
    return Revaluation(
        foreign=foreign,
        carrying=carrying,
        revalued=revalued,
        gain_loss=swing,
    )
