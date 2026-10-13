**English** · [Magyar](../hu/09-outcome.md) · [↑ README](../../README.md)

# Outcome

## Where it stands (2026-10-13)

- **In use since March 2026**, refreshed every quarter. A refresh — new workbooks in, ETL run, new
  partners' countries checked, report numbers recomputed — takes about an hour.
- **The bank accepted the numbers.** The report built on the database went to the bank, and the
  bank was satisfied with it; the purpose of the transaction is not part of this case study.
- **The bank report** is in its **seventh version**. Every version since v4 is
  kept side by side.
- **The gate keeps working.** The first import of each year showed where the dirt was: 104, 167
  and 26 blocking issues in the oldest, CRM-era years (2020–2022), 0–9 in 2023–2026. The oldest
  years were later taken out of the load. In the active years the gate still stops a handful of
  rows per import — almost always a won deal typed without its work number — which go back to the
  source and are fixed within a day.
- **The second loop** (the order register, June 2026) produced its own error list — orders without
  a quote, won quotes without an order number — and is still being worked down on the client side.

## What worked

| | why it mattered |
|---|---|
| fixing errors in the source, not in the DB | the data got better at the root; nothing had to be re-patched after a rebuild |
| the operator DB as the home of judgement | every merge and country decision survived dozens of rebuilds |
| zones instead of a single threshold | the operator only saw the names that needed a person |
| "recompute, never copy" | caught real changes between versions that a copied table would have hidden |
| explicit business definitions | a number in the report can be traced to one written rule |

## Honest gaps — and what happened to them

| gap | found | status |
|---|---|---|
| **No automated tests.** Correctness rests on cross-checks printed at the end of every ETL run and on comparing each report against the previous one. | from the start | open — the first candidates are the name normaliser and the status mapper, with synthetic cases |
| **The domestic/foreign flag from the spreadsheet beat the country name**, and the operator's manual country decisions were not passed to the quote-level transform. A whole year's domestic/foreign split was off by ~16% of its quoted value. | 2026-10-13, while preparing a report | **fixed**; it affected the domestic/foreign split of one year in every earlier report version; v7 corrects it with a change note |
| **Operator-added statuses were saved but never applied** — the transform only read the built-in map. | 2026-10-13, code review for this case study | **fixed** |
| **The derived alias table grew on every run** (no unique key, so "insert or ignore" never ignored). 13.7k rows for ~4.5k real aliases. | 2026-10-13, code review | **fixed** (dedupe + unique index) |
| **The incremental load was not atomic.** SQLite's `executescript` commits implicitly, so a failure after the per-year delete could lose that year. | 2026-10-13, hiring-manager review of this case study | **fixed** (snapshot + restore; tested with a forced failure) |
| **The override reason was required only by the form**, not by the server. | 2026-10-13, same review | **fixed** |
| **Two partner-ID schemes coexist** in the derived DB (standalone runs vs. wizard runs); unused partner rows are never cleaned up. | 2026-10-13, code review | open — harmless for the numbers (quotes reference the right ID), untidy |
| **A one-off analysis script was lost.** The "new partner per year" table was computed in a session script that was never saved; reconstructing it reproduced one product group exactly and the other within ±3 partners per year. | 2026-10-13 | lesson taken — now that the routine is stable, its queries belong in a versioned script |
| **Docs drift.** Some docstrings and the project notes described earlier states (full rebuild instead of incremental load, an older JSON shape). | 2026-10-13, code review | being corrected |
| **Requested but not delivered:** industry breakdown, loss reasons by cause, partner enrichment beyond the country. | — | shelved deliberately (see [At a glance](00-at-a-glance.md#plan-vs-built)) |

## What I would do differently

1. **Tests first for the two hearts of the system** — the name normaliser and the status mapper —
   built on a synthetic set of the real error types. The status-dictionary bug would have been
   caught by a test of the mapper; the country bug by one asserting that domestic/foreign always
   follows the country name. Neither needed more than a few lines.
2. **One partner-ID scheme from day one.** The standalone ETL and the operator wizard grew their
   own ID prefixes; it works, but it is a seam.
3. **Promote a routine to code the moment it repeats.** I kept the bank report deliberately manual
   while its shape was moving — right call — but the third quarterly refresh was the signal to
   save its queries as a script, and I took it one quarter late.

## Plan vs built

| planned | built |
|---|---|
| a dashboard | a dashboard, plus the part that made it trustworthy: the cleaning pipeline and the operator loop |
| one-off cleaning | a repeatable quarterly routine |
| automated report | a hand-written report on automated numbers — on purpose, until the shape settled |
