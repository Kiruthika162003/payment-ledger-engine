"""Withholding: paying a contractor less because the tax goes straight to the state.

When a payer is obliged to withhold tax, the contractor is owed the
gross amount but receives the net, and the difference goes to the
tax authority in the contractor's name. Getting this wrong in
either direction is expensive: under-withholding leaves the payer
liable for tax they failed to collect, and over-withholding
short-pays a supplier who will notice. This module computes the
withheld amount and the net payment, and it keeps the accounting
identity that the net plus the withheld equals the gross exactly,
which is what lets the contractor's certificate and the payer's
remittance agree to the cent. It also does the gross-up, the case
where a contract promises a specific net and the payer must
therefore pay a larger gross so that after withholding the promised
net arrives; the arithmetic is net over one minus the rate, and
rounding it down would leave the contractor a cent short every
time, so it rounds up. A rate of one or more is refused, since
withholding the entire payment leaves nothing to pay and a gross-up
at that rate is a division by zero dressed as a contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money, scale


@dataclass(frozen=True)
class WithholdingResult:
    gross: Money
    withheld: Money
    net: Money
    rate: Fraction

    def reconciles(self) -> bool:
        return self.net + self.withheld == self.gross


def _guard(rate: Fraction) -> None:
    if rate < 0:
        raise Refused("a withholding rate is not negative")
    if rate >= 1:
        raise Refused(
            "a withholding rate of one or more leaves nothing to pay; a "
            "gross-up at that rate is a division by zero dressed as a contract"
        )


def withhold(gross: Money, rate: Fraction) -> WithholdingResult:
    _guard(rate)
    if not gross.is_positive():
        raise Refused("withholding applies to a positive payment")
    withheld = scale(gross, rate, Rounding.HALF_EVEN)
    return WithholdingResult(gross=gross, withheld=withheld, net=gross - withheld, rate=rate)


def gross_up(target_net: Money, rate: Fraction) -> WithholdingResult:
    _guard(rate)
    if not target_net.is_positive():
        raise Refused("a gross-up targets a positive net payment")
    gross = round_money(
        Fraction(target_net.units) / (1 - rate), target_net.currency, Rounding.CEILING
    )
    result = withhold(gross, rate)
    if result.net < target_net:
        # Rounding up the gross should always clear the target; if a rate
        # ever leaves it short, add the shortfall rather than under-paying.
        shortfall = target_net - result.net
        return withhold(gross + shortfall, rate)
    return result


def certificate_lines(result: WithholdingResult) -> list[tuple[str, str]]:
    return [
        ("gross", result.gross.format(with_symbol=False)),
        ("withheld", result.withheld.format(with_symbol=False)),
        ("net paid", result.net.format(with_symbol=False)),
        ("rate", f"{float(result.rate * 100):g}%"),
    ]
