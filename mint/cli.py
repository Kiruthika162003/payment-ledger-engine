"""The command line over the assays: list them, check them, summarize them.

The verification organ needs a door that a person and a continuous
integration job can both walk through, so this module exposes the
three commands the house style settles on. Listing prints every
assay and the question it answers, so a reader can see the claims
without running them. Checking runs them all and exits nonzero the
moment one is broken, which is the form a build gate wants.
Summary runs them all and prints the one line that says how many
exist and how many are broken, which is the form a human glancing
at the terminal wants. The commands share one run so the numbers
they report can never disagree with each other.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from mint.assays import broken, catalog

    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else "summary"
    assays = catalog()

    if command == "list":
        for item in assays:
            print(f"{item.name}: {item.question}")
        return 0

    if command == "check":
        failing = broken()
        for item in failing:
            print(f"BROKEN {item.name}: {item.question}")
            for finding in item.findings():
                if not finding.holds():
                    print(finding.render())
        if failing:
            print(f"{len(failing)} assay(s) broken")
            return 1
        print("all assays hold")
        return 0

    if command == "summary":
        failing = broken()
        print(f"{len(assays)} assays ({len(failing)} broken)")
        return 1 if failing else 0

    print(f"unknown command {command!r}; try list, check, or summary")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
