"""The refusals: a ledger says no with a sentence, never with a silent zero.

A payment ledger is trusted precisely because it refuses the
operations that would make it lie, and the shape of those
refusals is part of the design rather than an afterthought. The
base of the hierarchy is a refusal that carries a full sentence
naming the situation and, wherever there is one, the remedy,
because an error that reads "invalid amount" tells an operator
nothing they can act on while one that reads "a capture of 12.00
exceeds the 10.00 still held on this authorization" tells them
exactly what went wrong and by how much. The subclasses exist so
that calling code can distinguish the handful of situations it
genuinely wants to branch on, an unbalanced entry from a currency
mismatch from an unknown account, without parsing prose, but every
one of them still carries the human sentence for the log and the
operator. The rule the whole package holds to is that money is
never silently coerced, dropped, or invented: an operation that
cannot be performed honestly raises rather than returning a
plausible-looking wrong number, because a ledger that guesses is
worse than one that stops.
"""

from __future__ import annotations


class LedgerError(Exception):
    """The root of every error the ledger raises on purpose."""


class Refused(LedgerError):
    """An operation the ledger declined, with the reason in the message."""


class Unbalanced(Refused):
    """A journal entry whose postings do not sum to zero per currency."""


class CurrencyMismatch(Refused):
    """Arithmetic or comparison attempted across two different currencies."""


class UnknownCurrency(Refused):
    """A currency code the registry has never been told about."""


class UnknownAccount(Refused):
    """A posting or query naming an account the book does not hold."""


class DuplicateAccount(Refused):
    """An attempt to open an account whose code is already in the chart."""


class InsufficientFunds(Refused):
    """A withdrawal, capture, or hold larger than the balance allows."""


class StaleRate(Refused):
    """A conversion requested against an exchange rate that is missing or expired."""


class AlreadyPosted(Refused):
    """A second attempt to commit an entry the ledger has already recorded."""
