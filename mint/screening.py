"""Name screening: fuzzy matches go to a person, never straight to a refusal.

Screening a customer against a watchlist is a matching problem with
an asymmetric cost. A missed match may be a regulatory breach; a
false match freezes an innocent person who happens to share a name
with someone sanctioned, and there are a great many people named
Mohammed Ahmed. The resolution the industry settled on is that
fuzzy matching produces candidates for a human to clear, never an
automatic refusal, and this module is built that way: it scores
similarity and returns candidates with their scores, and the only
thing it will state without a human is that a name did not match at
all. Scoring combines exact token overlap with an edit-distance
allowance, so a transposed pair of letters or a missing middle name
still surfaces, and the threshold is a parameter because the right
setting depends on how much review capacity exists. Normalization
strips punctuation and case and orders tokens, since a list holding
a name surname-first and a customer record holding it the other way
are the same person and a naive comparison says they are not.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused


def normalize_name(name: str) -> tuple[str, ...]:
    cleaned = "".join(char if char.isalnum() or char.isspace() else " " for char in name)
    tokens = [token for token in cleaned.upper().split() if token]
    return tuple(sorted(tokens))


def edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, start=1):
        current = [i]
        for j, b in enumerate(right, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (a != b),
                )
            )
        previous = current
    return previous[-1]


def token_similarity(left: str, right: str) -> Fraction:
    if left == right:
        return Fraction(1)
    longest = max(len(left), len(right))
    if longest == 0:
        return Fraction(1)
    distance = edit_distance(left, right)
    if distance >= longest:
        return Fraction(0)
    return Fraction(longest - distance, longest)


def name_similarity(left: str, right: str) -> Fraction:
    left_tokens = normalize_name(left)
    right_tokens = normalize_name(right)
    if not left_tokens or not right_tokens:
        return Fraction(0)
    total = Fraction(0)
    for token in left_tokens:
        best = max(
            (token_similarity(token, other) for other in right_tokens),
            default=Fraction(0),
        )
        total += best
    return total / len(left_tokens)


@dataclass(frozen=True)
class WatchEntry:
    id: str
    name: str
    programme: str


@dataclass(frozen=True)
class Candidate:
    entry_id: str
    entry_name: str
    programme: str
    score: Fraction

    def percent(self) -> int:
        return int(self.score * 100)


@dataclass(frozen=True)
class ScreeningResult:
    subject: str
    candidates: tuple[Candidate, ...]

    def is_clear(self) -> bool:
        # The only verdict this module states without a human.
        return not self.candidates

    def best(self) -> Candidate | None:
        if not self.candidates:
            return None
        return self.candidates[0]

    def needs_review(self) -> bool:
        return bool(self.candidates)


def screen(
    subject: str, watchlist: list[WatchEntry], threshold: Fraction = Fraction(85, 100)
) -> ScreeningResult:
    if threshold <= 0 or threshold > 1:
        raise Refused("a screening threshold is a fraction above zero and at most one")
    if not subject.strip():
        raise Refused("a screening needs a name to screen")
    found: list[Candidate] = []
    for entry in watchlist:
        score = name_similarity(subject, entry.name)
        if score >= threshold:
            found.append(Candidate(entry.id, entry.name, entry.programme, score))
    found.sort(key=lambda item: (-item.score, item.entry_id))
    return ScreeningResult(subject=subject.strip(), candidates=tuple(found))
