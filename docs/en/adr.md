**English** · [Magyar](../hu/adr.md) · [↑ README](../../README.md) · [At a glance](00-at-a-glance.md)

# Architecture decision records

Fifteen decisions that shaped the system, in a fixed form: **context · decision · rejected
alternatives · consequences · status**. Numbers match [At a glance](00-at-a-glance.md).

> The project did not keep formal decision records while it ran; the decisions themselves are
> documented in the code comments and project notes. These records were written for this case
> study, and the *rejected* lines restate the reasoning given at the time — they are not minutes of
> a formal evaluation.

---

### ADR-01 — Layout knowledge lives in one config registry

- **Context.** Every year's workbook had a different column layout; older years had no status column.
- **Decision.** A column map per layout era, a file entry per year (file, sheet or sheets, start
  row, map). The extractor is generic.
- **Rejected.** Per-year reader functions (copy-paste drift); header-name detection (headers were
  reworded, merged and multi-line — less reliable than a person looking once).
- **Consequences.** A new year is a config entry; a new layout is a short map. Someone still has
  to look at the sheet.
- **Status.** Held. → [Ingestion](02-ingestion.md)

### ADR-02 — Two databases: derived vs remembered

- **Context.** Merge decisions, country decisions and new statuses are human judgement; the
  analytics tables are rebuilt from the workbooks.
- **Decision.** The analytics DB is fully derived and disposable; the operator DB holds every human
  decision and survives every rebuild. Nothing in the analytics DB is edited by hand.
- **Rejected.** One database with "protected" tables (one wrong reset away from losing months of
  decisions).
- **Consequences.** The ETL reads the operator DB on every run; two files to understand; one to back up.
- **Status.** Held. → [Data model](04-data-model.md)

### ADR-03 — Errors are fixed in the source

- **Context.** The errors are typed in continuously by the people who keep the workbooks.
- **Decision.** The quality gate produces an error list for the spreadsheet owners; they fix the
  source; the files are re-imported.
- **Rejected.** Correcting values in the database or in a cleaning script (lost on rebuild,
  invisible to the people who keep making the same error).
- **Consequences.** The loop waits on other people's time; the source gets better at the root.
- **Status.** Held. → [Operator workshop](05-operator-workshop.md)

### ADR-04 — Name matching in zones, a person decides the uncertain

- **Context.** A missed merge duplicates a customer (visible); a wrong merge moves revenue between
  customers (invisible).
- **Decision.** Normalise, score by similarity, auto-accept ≥ 0.95, everything below goes to the
  operator. Short names are never auto-merged.
- **Rejected.** One automatic threshold; ML-based matching (unexplainable to the operator, no
  labelled data, and the volume did not need it).
- **Consequences.** Hundreds of decisions at the first import, a handful later.
- **Status.** Held. → [Entity resolution](03-entity-resolution.md)

### ADR-05 — Every raw spelling is kept as an alias

- **Decision.** Each spelling ever seen is stored against its canonical partner, with its source.
- **Rejected.** Overwriting names with the canonical one (loses the trail; the same typo next year
  asks again).
- **Consequences.** Next year's typo is an exact hit; the alias table must be kept clean (it once
  grew on every run — fixed in October 2026 with a unique key).
- **Status.** Held.

### ADR-06 — A blocking quality gate with override-by-reason

- **Decision.** Two severities. Blocking: won without a work number, unmatched partner. Warning:
  missing country, missing date, slow reaction. A blocking issue can be overridden only with a
  written reason, stored with the session.
- **Rejected.** Warn-only (the won-without-work-number error would flow straight into the realised
  revenue reconciliation); block-everything (every import would stall).
- **Status.** Held.

### ADR-07 — Status as a mapping table, extensible by the operator

- **Decision.** 42 raw spellings → 10 states with explicit open / won / lost flags in code; new
  spellings added by the operator into a status dictionary, applied by the ETL.
- **Consequences.** Two places to look. Until October 2026 the ETL ignored the operator's
  dictionary — a gap found during this write-up and fixed.
- **Status.** Held, fixed.

### ADR-08 — Incremental load per product group × year

- **Decision.** Only the (product group, year) pairs in the current import are replaced.
- **Rejected.** Full rebuild on every run (re-imports touch closed years; slower; a partial upload
  would wipe the rest).
- **Consequences.** Removing a year needs an explicit delete.
- **Status.** Held.

### ADR-09 — Logic in SQL views, a versioned JSON contract to the page

- **Decision.** Numbered SQL views hold the business logic; a JSON file with a contract version and
  a per-section source map is the only thing the page sees.
- **Rejected.** Computing metrics in the page's JavaScript (untraceable; drifts from the report).
- **Consequences.** A metric change is an SQL change; the report and the page share definitions.
- **Status.** Held; contract v2 since October 2026.

### ADR-10 — Country = the entity we transact with

- **Context.** The domestic/foreign split is the bank report's core question; registry country and
  market reality differ for multinationals.
- **Decision.** Country is the entity we actually deal with; domestic/foreign is always derived
  from it; manual decisions override everything; system proposals are only proposals.
- **Rejected.** Registry/HQ country (analytically wrong for this question); trusting the
  spreadsheet's domestic flag (it contradicted the country name).
- **Consequences.** A methodology note on every external country split.
- **Status.** Held; the "flag beats name" bug fixed October 2026.

### ADR-11 — Two year bases, never merged

- **Decision.** Funnel by request year; realised orders by register year with accrual; win rate by
  outcome year. Shown side by side, explained.
- **Rejected.** One "won" figure (simpler, and wrong for one of the two questions a bank asks).
- **Status.** Held. → [Business definitions](06-business-definitions.md)

### ADR-12 — Live pipeline = quoted within 12 months

- **Decision.** Open quotes older than 12 months (counted back from the latest request in the data)
  are stale — listed for closing, not counted.
- **Rejected.** All open quotes (years-old quotes inflated the pipeline); a per-quote expiry date
  (not recorded in the source).
- **Status.** Held since October 2026.

### ADR-13 — No guessed data

- **Decision.** If the data is not there, the chart is not there.
- **Consequences.** The industry breakdown was removed when enrichment coverage turned out to be ~0%.
- **Status.** Held.

### ADR-14 — Don't automate before there is a routine

- **Decision.** Workstreams run in the mode their maturity allows: the dashboard is code-driven, the
  bank report is hand-written on DB-computed numbers, the company-register analysis is exploratory.
- **Rejected.** Generating the report from day one (its shape changed every version).
- **Consequences.** Manual work each quarter; the queries should now be promoted to a script (see
  [Outcome](09-outcome.md)).
- **Status.** Held.

### ADR-15 — SQLite files and a small Flask app, one operator

- **Context.** One operator, a quarterly cycle, a few thousand quotes, workbooks on a local disk.
  *(Not in the at-a-glance table — added after review, because it is the first question people ask.)*
- **Decision.** Two SQLite files, a Python ETL with two external dependencies (openpyxl, Flask), a
  single-file HTML page — runnable on the operator's Windows PC with a double-click.
- **Not chosen.** A database server, a BI platform, a transformation framework: nothing in the
  volume or the single-operator use needed one, and each would have added infrastructure to run.
- **Consequences.** Designed for one operator at a time — concurrent imports are not guarded; the
  analytics DB is a file that can be deleted and rebuilt in minutes.
- **Status.** Held.
