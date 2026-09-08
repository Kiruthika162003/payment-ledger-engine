"""Scenarios and sensitivity: which assumption is actually driving the answer.

A model produces one number and hides how much that number depends
on each thing it was told. Scenarios and sensitivity are the two
ways to expose it. A scenario changes several assumptions together
into a coherent story, the downside case, and reports the result;
sensitivity changes one assumption at a time and reports how far
the answer moved, which is what identifies the assumption worth
arguing about. Both are here because they answer different
questions and are routinely confused: a scenario tells you what
happens if the world is worse, and a sensitivity tells you which
of your guesses you should go and check. The sensitivity ranking
is the useful output, since a model with twenty inputs usually
turns on two of them, and the other eighteen can be left alone.
Assumptions are named and typed as fractions so a run is
reproducible, and an assumption a scenario overrides but the model
never declared is refused rather than silently ignored, since a
typo in an override is otherwise invisible.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money


@dataclass
class Model:
    name: str
    assumptions: dict[str, Fraction] = field(default_factory=dict)
    compute: Callable[[dict[str, Fraction]], Money] | None = None

    def declare(self, key: str, value: Fraction) -> Fraction:
        if not key.strip():
            raise Refused("an assumption needs a name")
        self.assumptions[key.strip()] = value
        return value

    def run(self, overrides: dict[str, Fraction] | None = None) -> Money:
        if self.compute is None:
            raise Refused(f"model {self.name!r} has nothing to compute")
        values = dict(self.assumptions)
        for key, value in (overrides or {}).items():
            if key not in values:
                raise Refused(
                    f"the override {key!r} names an assumption this model never "
                    "declared; a typo in an override is otherwise invisible"
                )
            values[key] = value
        return self.compute(values)

    def base_case(self) -> Money:
        return self.run()


@dataclass(frozen=True)
class Scenario:
    name: str
    overrides: dict[str, Fraction]

    def apply_to(self, model: Model) -> Money:
        return model.run(self.overrides)


@dataclass(frozen=True)
class SensitivityResult:
    assumption: str
    low_result: Money
    high_result: Money
    base_result: Money

    def swing(self) -> Money:
        return self.high_result - self.low_result

    def magnitude(self) -> int:
        return abs(self.swing().units)

    def is_material(self, threshold: Money) -> bool:
        return self.magnitude() >= abs(threshold.units)


def compare_scenarios(model: Model, scenarios: list[Scenario]) -> list[tuple[str, Money]]:
    rows = [("base", model.base_case())]
    for scenario in scenarios:
        rows.append((scenario.name, scenario.apply_to(model)))
    return rows


def sensitivity(
    model: Model, assumption: str, low: Fraction, high: Fraction
) -> SensitivityResult:
    if assumption not in model.assumptions:
        raise Refused(f"the model never declared {assumption!r}")
    if low > high:
        raise Refused("a sensitivity range runs from low to high")
    return SensitivityResult(
        assumption=assumption,
        low_result=model.run({assumption: low}),
        high_result=model.run({assumption: high}),
        base_result=model.base_case(),
    )


def rank_sensitivities(
    model: Model, ranges: dict[str, tuple[Fraction, Fraction]]
) -> list[SensitivityResult]:
    # The ranking is the point: a model with twenty inputs usually turns on
    # two of them and the rest can be left alone.
    results = [
        sensitivity(model, name, low, high) for name, (low, high) in ranges.items()
    ]
    return sorted(results, key=lambda result: -result.magnitude())


def dominant_assumption(
    model: Model, ranges: dict[str, tuple[Fraction, Fraction]]
) -> str | None:
    ranked = rank_sensitivities(model, ranges)
    return ranked[0].assumption if ranked else None
