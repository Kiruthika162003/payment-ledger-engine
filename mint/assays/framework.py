"""The assay framework: a claim about the ledger that holds only if the numbers agree.

An assay is a coin test. A mint does not trust that its coins are
pure because the process was designed to make them pure; it draws
one and measures it. The verification organ here works the same
way: each assay states a question about a load-bearing property of
the ledger, runs a real scenario through the real code, and
records the numbers it measured beside the numbers it expected. An
assay holds only when every one of its findings matches, and a
finding that does not match is reported as broken rather than
quietly passed. The house rule the whole repository is built on
lives here: when a measurement refutes a guess, the guess is not
erased, it is rewritten into the expected value with the
correction noted in the module that made it, so the record shows
what was believed and what turned out to be true. The framework
itself holds no cleverness on purpose, because a verification
organ that is hard to trust is worse than none, and the only way
to trust it is to be able to read the whole of it in one sitting.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    label: str
    measured: object
    expected: object

    def holds(self) -> bool:
        return self.measured == self.expected

    def render(self) -> str:
        verdict = "holds" if self.holds() else "BROKEN"
        return (
            f"    {self.label}: measured {self.measured!r}, "
            f"expected {self.expected!r} [{verdict}]"
        )


@dataclass(frozen=True)
class Assay:
    name: str
    question: str
    probe: Callable[[], list[Finding]]

    def findings(self) -> list[Finding]:
        return self.probe()

    def holds(self) -> bool:
        return all(finding.holds() for finding in self.findings())


_ASSAYS: list[Assay] = []


def assay(name: str, question: str) -> Callable[[Callable[[], list[Finding]]], Callable]:
    def register(probe: Callable[[], list[Finding]]) -> Callable[[], list[Finding]]:
        if any(existing.name == name for existing in _ASSAYS):
            raise ValueError(f"an assay named {name!r} is already registered")
        _ASSAYS.append(Assay(name=name, question=question, probe=probe))
        return probe

    return register


def catalog() -> tuple[Assay, ...]:
    return tuple(_ASSAYS)


def broken() -> tuple[Assay, ...]:
    return tuple(item for item in _ASSAYS if not item.holds())
