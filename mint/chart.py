"""The chart of accounts: the tree that organizes every account by code.

A chart of accounts is the index of a business's books, a tree of
accounts each identified by a code, and it enforces a few rules
that keep reports honest. An account code is unique, because two
accounts sharing a code would let a posting land in either and a
balance mean neither. A child account inherits its parent's type,
since a sub-account of cash is still an asset and letting a
liability hang under an asset would corrupt every rollup that sums
a parent from its children. A parent must exist before a child
names it, which turns a typo in a parent code into an immediate
refusal rather than an orphan that silently never rolls up. The
chart offers the two traversals reports actually need, the direct
children of a node and the full set of descendants under it, so a
balance sheet can present cash and its sub-accounts as one line
with the detail underneath. The chart holds structure only, not
balances; balances come from folding the ledger's postings, which
keeps the chart a stable description of shape while the numbers
move underneath it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mint.accounts import Account, AccountType
from mint.errors import DuplicateAccount, Refused, UnknownAccount


@dataclass
class Chart:
    accounts: dict[str, Account] = field(default_factory=dict)

    def open(self, account: Account) -> Account:
        if account.code in self.accounts:
            raise DuplicateAccount(
                f"account {account.code!r} is already open; a code names "
                "exactly one account or a balance means nothing"
            )
        if account.parent is not None:
            parent = self.accounts.get(account.parent)
            if parent is None:
                raise UnknownAccount(
                    f"account {account.code!r} names parent "
                    f"{account.parent!r}, which is not in the chart; open "
                    "the parent before its children"
                )
            if parent.type is not account.type:
                raise Refused(
                    f"account {account.code!r} is a {account.type.value} "
                    f"under a {parent.type.value} parent; a sub-account "
                    "keeps its parent's type"
                )
        self.accounts[account.code] = account
        return account

    def add(
        self,
        code: str,
        name: str,
        account_type: AccountType,
        currency: str,
        parent: str | None = None,
    ) -> Account:
        return self.open(Account(code, name, account_type, currency, parent))

    def get(self, code: str) -> Account:
        if code not in self.accounts:
            raise UnknownAccount(
                f"the chart has no account {code!r}; open it before posting to it"
            )
        return self.accounts[code]

    def has(self, code: str) -> bool:
        return code in self.accounts

    def children(self, code: str) -> list[Account]:
        self.get(code)
        return sorted(
            (a for a in self.accounts.values() if a.parent == code),
            key=lambda a: a.code,
        )

    def descendants(self, code: str) -> list[Account]:
        self.get(code)
        out: list[Account] = []
        frontier = self.children(code)
        while frontier:
            node = frontier.pop()
            out.append(node)
            frontier.extend(self.children(node.code))
        return sorted(out, key=lambda a: a.code)

    def roots(self) -> list[Account]:
        return sorted(
            (a for a in self.accounts.values() if a.parent is None),
            key=lambda a: a.code,
        )

    def of_type(self, account_type: AccountType) -> list[Account]:
        return sorted(
            (a for a in self.accounts.values() if a.type is account_type),
            key=lambda a: a.code,
        )
