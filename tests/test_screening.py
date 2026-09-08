from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.screening import (
    WatchEntry,
    edit_distance,
    name_similarity,
    normalize_name,
    screen,
)


def _watchlist():
    return [
        WatchEntry("W1", "Mohammed Ahmed", "sanctions"),
        WatchEntry("W2", "Jane Elizabeth Smith", "pep"),
        WatchEntry("W3", "Acme Trading Company", "sanctions"),
    ]


class TestNormalization:
    def test_case_and_punctuation_are_stripped(self):
        assert normalize_name("Jane E. Smith") == normalize_name("JANE E SMITH")

    def test_token_order_does_not_matter(self):
        assert normalize_name("Smith, Jane") == normalize_name("Jane Smith")

    def test_an_empty_name_normalizes_to_nothing(self):
        assert normalize_name("   ") == ()


class TestDistance:
    def test_identical_strings_are_zero_apart(self):
        assert edit_distance("SMITH", "SMITH") == 0

    def test_a_transposition_costs_two(self):
        assert edit_distance("SMITH", "SMTIH") == 2

    def test_a_missing_letter_costs_one(self):
        assert edit_distance("SMITH", "SMIH") == 1


class TestSimilarity:
    def test_an_exact_name_scores_one(self):
        assert name_similarity("Jane Smith", "Smith Jane") == Fraction(1)

    def test_a_typo_still_scores_high(self):
        # One token matches exactly and the transposed one scores three
        # fifths, so the average is exactly four fifths, not above it.
        assert name_similarity("Jane Smtih", "Jane Smith") == Fraction(4, 5)

    def test_unrelated_names_score_low(self):
        assert name_similarity("Jane Smith", "Acme Trading") < Fraction(5, 10)


class TestScreening:
    def test_an_unrelated_name_is_clear(self):
        result = screen("Bartholomew Zylk", _watchlist())
        assert result.is_clear()
        assert not result.needs_review()

    def test_an_exact_hit_surfaces_as_a_candidate(self):
        result = screen("Mohammed Ahmed", _watchlist())
        assert result.needs_review()
        assert result.best().entry_id == "W1"

    def test_a_near_miss_still_surfaces(self):
        result = screen("Mohamed Ahmed", _watchlist(), threshold=Fraction(8, 10))
        assert result.needs_review()

    def test_it_never_states_a_block_itself(self):
        result = screen("Mohammed Ahmed", _watchlist())
        # The only verdict without a human is the negative one.
        assert not result.is_clear()
        assert hasattr(result, "candidates")

    def test_candidates_are_ordered_by_score(self):
        watchlist = [
            WatchEntry("A", "Jane Smith", "pep"),
            WatchEntry("B", "Jane Elizabeth Smith", "pep"),
        ]
        result = screen("Jane Smith", watchlist, threshold=Fraction(5, 10))
        assert result.candidates[0].entry_id == "A"

    def test_the_score_is_reportable_as_a_percent(self):
        result = screen("Mohammed Ahmed", _watchlist())
        assert result.best().percent() == 100

    def test_a_missing_programme_still_carries_through(self):
        result = screen("Acme Trading Company", _watchlist())
        assert result.best().programme == "sanctions"


class TestRefusals:
    def test_an_empty_subject_is_refused(self):
        with pytest.raises(Refused):
            screen("   ", _watchlist())

    def test_a_zero_threshold_is_refused(self):
        with pytest.raises(Refused):
            screen("Jane", _watchlist(), threshold=Fraction(0))
