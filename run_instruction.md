# Running payment-ledger-engine

A double entry payment ledger where every posting balances, written in Python. This file covers how to build
the project, run its tests, and execute it. Every command below was run from a
clean checkout of this repository before being written down.

## Requirements

Python 3.11 or newer. There are no third party runtime dependencies.

## Setup

Nothing to install. The package has no dependencies, so every command below
runs from the repository root against the source tree as it stands.

## Run the tests

```bash
python -m pytest -q
```

The suite is the primary check. It runs from the repository root with no
arguments and no configuration, and it prints the number of tests it ran. A
non-zero exit status means something is wrong. Read the printed summary rather
than a shell pipeline, because piping the output through another command
replaces the real exit code with that of the last command in the pipe.

## Lint

```bash
python -m ruff check .
```

The lint configuration lives in `pyproject.toml`. It passes with no findings.

## Run the command line tool

The tool takes a bare subcommand and does not accept `--help`; passing one
prints `unknown command` and the list of what it does accept.

```bash
python -m mint.cli summary
```

The subcommands are `list`, `check`, `summary`.

For example:

```bash
python -m mint.cli list
```

## Run a worked example

There are 6 runnable examples in `examples/`. Each exposes `run()`, which
returns the lines it would print, and `main()`, which prints them:

```bash
python -c "from examples.coffee_day import main; main()"
```

The full list is `coffee_day`, `group_close`, `lending_desk`, `marketplace_day`, `month_end`, `payables_run`.

## Layout

- `mint/` the package itself
- `mint/assays/` the verification organ, a set of measured claims about the
  package as a whole rather than unit tests of one function
- `tests/` the test suite
- `examples/` runnable end to end scenarios

## Notes

The examples are pinned line by line in the test suite, so an example whose
output drifts fails the build rather than quietly changing. Where a guess about
behaviour was refuted by measurement, the wrong guess is kept in the source
beside the measured value rather than deleted.
