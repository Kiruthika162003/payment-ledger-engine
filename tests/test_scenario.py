from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.scenario import (
    Model,
    Scenario,
    compare_scenarios,
    dominant_assumption,
    rank_sensitivities,
    sensitivity,
)


def _model() -> Model:
    def compute(values: dict[str, Fraction]) -> Money:
        units = values["volume"] * values["price"] - values["fixed"]
        return Money.from_minor(int(units), "USD")

    model = Model("profit", compute=compute)
    model.declare("volume", Fraction(1000))
    model.declare("price", Fraction(500))
    model.declare("fixed", Fraction(200000))
    return model


class TestModel:
    def test_the_base_case_uses_the_declared_assumptions(self):
        assert _model().base_case() == Money.from_minor(300000, "USD")

    def test_an_override_changes_the_answer(self):
        model = _model()
        assert model.run({"volume": Fraction(500)}) == Money.from_minor(50000, "USD")

    def test_an_undeclared_override_is_refused(self):
        with pytest.raises(Refused) as caught:
            _model().run({"typo": Fraction(1)})
        assert "otherwise invisible" in str(caught.value)

    def test_a_model_with_nothing_to_compute_is_refused(self):
        with pytest.raises(Refused):
            Model("empty").run()

    def test_an_unnamed_assumption_is_refused(self):
        with pytest.raises(Refused):
            _model().declare("  ", Fraction(1))


class TestScenarios:
    def test_a_scenario_changes_several_assumptions_together(self):
        model = _model()
        downside = Scenario(
            "downside", {"volume": Fraction(700), "price": Fraction(450)}
        )
        assert downside.apply_to(model) < model.base_case()

    def test_comparing_scenarios_starts_at_the_base(self):
        rows = compare_scenarios(
            _model(), [Scenario("upside", {"volume": Fraction(1200)})]
        )
        assert rows[0][0] == "base"
        assert rows[1][0] == "upside"


class TestSensitivity:
    def test_a_sensitivity_moves_one_assumption(self):
        result = sensitivity(_model(), "volume", Fraction(800), Fraction(1200))
        assert result.low_result < result.base_result < result.high_result

    def test_the_swing_measures_the_range(self):
        result = sensitivity(_model(), "volume", Fraction(800), Fraction(1200))
        assert result.swing() == Money.from_minor(200000, "USD")

    def test_an_undeclared_assumption_is_refused(self):
        with pytest.raises(Refused):
            sensitivity(_model(), "ghost", Fraction(1), Fraction(2))

    def test_a_backward_range_is_refused(self):
        with pytest.raises(Refused):
            sensitivity(_model(), "volume", Fraction(1200), Fraction(800))

    def test_materiality_compares_against_a_threshold(self):
        result = sensitivity(_model(), "volume", Fraction(800), Fraction(1200))
        assert result.is_material(Money.from_minor(1000, "USD"))
        assert not result.is_material(Money.from_minor(999999, "USD"))


class TestRanking:
    def _ranges(self):
        return {
            "volume": (Fraction(900), Fraction(1100)),
            "price": (Fraction(490), Fraction(510)),
            "fixed": (Fraction(199000), Fraction(201000)),
        }

    def test_the_ranking_puts_the_biggest_swing_first(self):
        ranked = rank_sensitivities(_model(), self._ranges())
        assert ranked[0].magnitude() >= ranked[-1].magnitude()

    def test_the_dominant_assumption_is_named(self):
        assert dominant_assumption(_model(), self._ranges()) in (
            "volume",
            "price",
            "fixed",
        )

    def test_an_empty_ranking_has_no_dominant_assumption(self):
        assert dominant_assumption(_model(), {}) is None

    def test_every_assumption_is_ranked(self):
        assert len(rank_sensitivities(_model(), self._ranges())) == 3
