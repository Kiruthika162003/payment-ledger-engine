# mint

A double-entry payment ledger engine, written in Python with no runtime dependencies.

Money is stored as whole minor units, never as a float. Every rate, ratio and
proportion is a `fractions.Fraction` carried exactly through the arithmetic and
rounded once, at the boundary, with the rounding mode named. Every division of a
sum uses largest-remainder allocation, so the parts add back to the whole. Every
journal entry balances before it is allowed into a ledger, and an operation that
cannot be performed correctly refuses with a sentence explaining what went wrong
rather than returning an approximate answer.

## What is in it

The package is built in layers from the bottom up.

**The core.** `money`, `currency` and `rounding` hold the base types: an amount
is an integer count of minor units plus a currency code, and the seven rounding
modes, `allocate` and `split` sit beside it. `accounts`, `chart`, `posting`,
`entry`, `ledger` and `book` build the double-entry machine on top: postings sum
to zero within an entry, entries land in a ledger, ledgers group into a book.

**Payments.** Authorization and capture, refunds, disputes and chargebacks,
gateways, settlement, idempotent posting, card validation, IBAN and routing
numbers, direct debits, interchange, merchant accounts, reserves, payout
schedules, velocity limits, wallets, gift cards, loyalty points, escrow and
marketplaces.

**Receivables and payables.** Invoices, bills, credit notes, terms and dunning,
aging, write-offs, payment allocation across open items, installments,
subscriptions and their lifecycle, remittance advice, collections and
customer deposits.

**Money over time.** Day-count conventions, interest, annuities, amortization,
leases, bonds, sinking funds, credit lines, factoring, depreciation, impairment,
asset retirement obligations, accruals, deferrals, prepayments, provisions and
their discounting.

**Tax.** VAT, withholding, jurisdictions and brackets, tax points, tax IDs, tax
provisions and loss carryforwards, deferred tax, and cash rounding at the till.

**Reporting.** Trial balance, statements, balance sheet, income statement, cash
flow, general ledger, ratios and KPIs, budgets and phasing, dimensions,
waterfall and cohort views, Benford analysis, discounted cash flow, break-even,
scenarios and forecasts.

**Groups and periods.** Entities, intercompany balances, translation,
consolidation, netting, transfer pricing, related parties, segments, period
close, reversals, opening balances and escheatment.

**Nonprofit and specialist ledgers.** Fund accounting with restricted balances,
endowments, pledges, memberships, gifts in kind with the three-part test for
donated services, barter with the commercial-substance test, unit pricing for
pooled funds and match funding against a finite pot.

Around all of it: an audit log with a tamper-evident hash chain, snapshots,
integrity checks, a query layer, batching, suspense accounts, bank
reconciliation, petty cash, duplicate detection, risk scoring, blocklists,
review queues, screening and verification.

## Assays

`mint/assays/` is the verification organ. An assay is a named question with a
probe that returns findings, and a finding is a measured value beside the value
it was expected to equal. They are not unit tests. A unit test asks whether one
function does what it says; an assay asks whether a claim about the whole
package still holds when the modules are put together, and answers with numbers.

Twenty of them hold at close:

```bash
python -c "from mint.cli import main; main(['list'])"
python -c "from mint.cli import main; main(['check'])"
python -c "from mint.cli import main; main(['summary'])"
```

`check` exits non-zero if any assay is broken. The questions include whether
every division in the package puts the whole sum back, whether money held for
other people stays held, whether everything deferred is released exactly once
and in full, whether every amount lands in exactly one period and the right one,
and whether the audit chain catches an altered record at the right index.

## Examples

`examples/` holds six worked ledgers, each a `run()` returning the lines it
prints. Their transcripts are pinned line by line in `tests/test_examples.py`, so
an example that drifts fails the suite:

- `coffee_day` a small shop from open to close
- `month_end` accruals, deferrals, depreciation and the close
- `marketplace_day` platform, sellers, fees and payouts
- `payables_run` bills, terms, discounts and a payment run
- `lending_desk` a loan book with interest and provisions
- `group_close` two entities, intercompany, translation, consolidation

## Running it

```bash
python -m pytest tests/ -q
```

```bash
python -m ruff check mint/ tests/ examples/
```

```bash
python -c "from examples.coffee_day import main; main()"
```

Python 3.11 or newer. Nothing to install.

## How it was built

Every module carries a docstring written as prose, stating what the module
claims about its part of the problem and, where the design is contentious, why
it refuses the easier alternative. Comments are sparse and reserved for the
places where the code would otherwise read as a mistake.

Where a guess about behaviour was refuted by running the code, the wrong guess
stays in the file beside the measured truth. There are a number of these. A
ninety-day-overdue receivable falls in the sixty-one-to-ninety bucket, not past
ninety, because the upper edge is inclusive. A hundred dollars split three ways
gives 3334, 3333 and 3333 minor units, not thirty-four dollars and two
thirty-threes. At twenty-four percent a year, a two percent minimum payment is
exactly the interest, so the balance never clears; that one became its own named
test. Three one-dollar gifts against a ten-dollar matching pot take three
dollars, not the pot, because the promise and not the pot is the binding
constraint.

The tests also found real bugs, which are fixed and recorded in the commits
rather than quietly corrected: invoice numbers with a letter prefix never
matched their duplicates because leading zeros were stripped from the whole
string instead of within each run of digits; weighted-average inventory costed
sales at the blend but valued the remainder at original lot costs, so what was
bought did not equal what was sold plus what was held; a reserve release credited
money the hold had never removed from the available balance; and ten rounded
annual charges left an asset five cents short of written down, so the final year
now takes exactly the remainder.

## At close

- 30,225 strict lines, counting code only, excluding docstrings, comments and blank lines
- 189 modules in `mint/`, plus 22 in `mint/assays/`
- 2,378 tests across 188 test files, all passing
- 20 assays, none broken
- 6 worked examples with pinned transcripts
- 57 commits, none of them red

Written by Kiruthika Subramani in collaboration with Claude, Anthropic's AI assistant.
