**English** · [Magyar](../hu/08-metrics.md) · [↑ README](../../README.md)

# Metrics

Every number here was measured on **2026-10-13** on the live system, with the method named. Counts
only — no values, names or identifiers of the client's data. Where a number measures something
narrower than it sounds, the note says so.

## The code

| | | how measured |
|---|---:|---|
| Python | 7,612 lines | `git ls-files '*.py' \| xargs wc -l` (includes two utility scripts not in the excerpt) |
| SQL views | 9 files, 250 lines | `sql/views/*.sql` |
| operator web app | 28 routes, 11 templates (2,630 lines) | `grep -c "route("`; `admin/templates/**` |
| automated tests | **0** | see [Outcome](09-outcome.md) |

## The source and its drift

| | | how measured |
|---|---:|---|
| years of workbooks | 7 (2020–2026); 4 loaded (2023–2026) | `config.FILE_CONFIG`: 8 active entries + 4 archived (three years of product group 1, one of group 2) |
| column maps | 14 — 8 quote layouts, 5 partner-sheet layouts, 1 contact layout | names matching `_*_COLS_*` in `config.py` |
| status vocabulary | 42 raw spellings → 10 states | `len(STATUS_MAP)`, distinct targets |
| legal-form suffix patterns | 31 | `len(COMPANY_SUFFIXES)` |
| country-name map | 42 distinct keys | `len(COUNTRY_NAME_MAP)` (one key was duplicated in the source) |

## Volume (loaded years)

| | | how measured |
|---|---:|---|
| quote requests | 2,410 | `SELECT COUNT(*) FROM quotes` (2023–2026) |
| quote line items | 3,405 | `quote_lines` |
| order-register rows | 597 | `work_orders` (order × register year, three divisions) |

## Entity resolution and operator decisions

| | | how measured / note |
|---|---:|---|
| canonical partners | 991 | `partner_master` |
| stored spellings (after normalisation) | 1,146 | `partner_aliases`; unique per partner + normalised name, so *raw* spellings are more |
| partners with 2–9 spellings | 103 | aliases grouped by partner |
| partner merges after the fact | 3 | `partner_merges` |
| import sessions | 34 (16 completed, 2 aborted, the rest stopped at a step) | `import_sessions`, 4 March – 24 June 2026 |
| name checks — green / yellow / red | 6,131 / 17 / 906 | `staging_partners` by zone — **checks, not companies**: a name is checked again in every session that contains it |
| operator decisions on red names | 79 reassigned to an existing partner, 827 new partners | `staging_partners.decision` |
| quality-gate issues | 1,918 — 347 blocking, 1,571 warnings | `staging_issues` |
| blocking issues at each year's first import | 104 / 167 / 26 / 0 / 1 / 9 / 0–1 (2020 → 2026) | `staging_issues` × `import_sessions.files_json` |
| country decisions | 774 — **331 manual**, 443 system proposals | `country_resolutions` by method; only manual ones are applied as authoritative |
| derived anomalies flagged per run | 108 | `anomalies` (cross-year, slow reaction, missing country, won without work number, missing date, bad work number) |
| order-register error list | 112 items in 8 categories | `scripts/extract_work_orders.py` output |

## The fixes of October 2026

| | before | after |
|---|---:|---:|
| derived alias table | 13,701 rows (grew every run) | 4,475 rows, stable across runs |
| one year's domestic/foreign split of quoted value | ~16% on the wrong side | derived from the country, manual decisions applied |
| operator-added statuses applied by the ETL | no | yes |

## Operations

| | |
|---|---|
| in use since | March 2026 |
| refresh cycle | quarterly; ~1 hour per refresh plus writing the report |
| bank report | version 7; every version since v4 kept side by side |

## Plan vs built

| planned | measured |
|---|---|
| "the data is cleaned" | 1,918 gate issues and 923 human name decisions say what that took |
| "the system works" | no automated tests — correctness rests on run-time cross-checks and version-to-version comparison; named as the first gap |
