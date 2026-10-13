**English** · [Magyar](../hu/07-how-i-worked.md) · [↑ README](../../README.md)

# How I worked

## The split

| | |
|---|---|
| **I** | received the task; turned "we want a monthly dashboard" and later "we need numbers for the bank" into a plan — what the pipeline is made of, where truth lives, what is automated and what is not; made the business definitions with the client; ran every import and every refresh; reviewed every number before it left |
| **Claude** (AI coding agent) | wrote the code to that plan — I was responsible for the design, the review and every number that left; proposed implementations; ran the measurements and comparisons I asked for; flagged what looked wrong |
| **The spreadsheet owners** | kept typing the data, and fixed their sources from the error lists |

We built it together; the code is Claude's. The decisions in [At a glance](00-at-a-glance.md)
are mine.

## Timeline

| when (2026) | what |
|---|---|
| early March | the request (a monthly KPI review) → a written expectations spec (five core KPIs) → the plan |
| 3–12 March | ETL, SQL views, the operator app with its import wizard; first imports year by year; error lists to the spreadsheet owners; the bank-report brief arrives; report v4 |
| June | the order register connected (read-only extractor → reconciliation → go-live); report v5 |
| October | quarterly refresh; dashboard redesigned as one story page; the register folded into the ETL; report v6; the next day a status refresh, during which the country bug was found and fixed → v7 with a change note |

Since March the system runs on a **quarterly cycle**: new workbooks arrive → the previous ones are
archived → ETL → the new partners' countries are checked → the report numbers are recomputed and
the next version is written. About an hour of refresh, plus the writing.

## The rules I set for the agent

These were not style preferences; each one exists because something went wrong without it.

| rule | why |
|---|---|
| **Recompute every number from the database; never copy from the previous version.** | In June a table was carried over from the previous report instead of being recomputed. I caught it in review; from then on this was a hard rule. |
| **Never overwrite a delivered version.** Every report version has its own dated file. | A bank conversation refers back to what was sent; it must still exist exactly as sent. |
| **No guessed data.** If coverage is not there, the chart is not there. | The industry breakdown was removed rather than filled with estimates. |
| **Business definitions are mine to decide.** The agent proposes, flags the consequence, and asks. | Whether a silent quote counts as lost changes the win rate materially — that is not a technical choice. |
| **Flag, don't second-guess.** A suspicious value goes on a list for a person; the code does not "correct" it. | A plausible-looking automatic correction is the hardest error to find later. |
| **First diff the new source against the previous one.** | I want to know what changed before I look at what the numbers say. |
| **Validate a re-derived calculation against the previous version first.** | When a lost script had to be rebuilt, it had to reproduce the old numbers before its new ones were trusted. |
| **Don't automate a workstream before it has a stable routine.** | The bank report stayed hand-written while its shape was still moving. |

## Code and data, kept apart

The code lives in its own repository and is synced — **code only** — to a separate working folder
where the real data lives (`sync_code.sh` copies the Python, SQL and templates; it never copies a
database, an upload or a data file). Databases, uploads, generated pages and source workbooks are
excluded from version control.

This case study goes one step further: nothing from the client's data is in it at all — see
[Data protection](10-data-protection.md).

## Plan vs built

| planned | built |
|---|---|
| a one-off dashboard project | a quarterly operating routine that has run since March |
| the agent writes, I review the output | the agent writes, I review the output **and the numbers against the previous version** — that is where the real errors were caught |
