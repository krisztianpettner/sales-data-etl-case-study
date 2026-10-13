**English** · [Magyar](README.hu.md)

# From spreadsheet chaos to a bank-grade dataset — a sales-data ETL case study

**[Krisztián Pettner](https://github.com/krisztianpettner)** · systems architect · [LinkedIn](https://www.linkedin.com/in/krisztian-pettner/)

> A manufacturing company tracked its quote requests for years in free-form Excel sheets, typed by
> hand, with no input validation. The task: turn that into a dataset solid enough for analysis,
> for preparing business decisions, and for **supporting a bank transaction**. I turned the request
> into a plan and was responsible for the design, the review and every number that left the system;
> Claude wrote the code, and we built it together. It has been in use since
> March 2026 and is refreshed every quarter. This repository shows **how the data was made
> trustworthy** — not the data itself.

## In 30 seconds

**The mess.** Seven years (2020–2026) of quote-tracking workbooks for two product groups. Every year the column
layout changed. Status was free text (40+ spellings for 10 states). The same customer appeared under
many names: legal suffix or none, with or without accents, abbreviated, misspelled. Some rows were
order line items pretending to be quotes; some values were in the wrong currency; for many partners
nobody had recorded the country.

**What the system does with it:**

| problem | answer in the architecture |
|---|---|
| column layout drifts every year | one config registry: a column map per layout era, a file entry per year — a new year is a config entry, not new code |
| the same company under many names | normalise → fuzzy match → **green / yellow / red zones** → a human decides the uncertain ones → canonical partner + alias table |
| human decisions must survive rebuilds | **two databases**: a disposable, fully derived analytics DB and a persistent operator DB for every human decision |
| errors live in the source, not in the code | an import wizard with a **blocking quality gate**; the error list goes back to the people who own the spreadsheets, they fix the source, we re-import |
| numbers must hold up in front of a bank | business definitions decided explicitly and written down (what is "open", what counts as "lost", which year a deal belongs to), numbers recomputed from the database every time |

**The principle behind it.** A missed merge shows up as two similar names in a list; a wrong merge
silently moves revenue from one customer to another. So the system **automates the cheap mistake
and leaves the expensive one to a person** — in name matching, in the quality gate, and in the
business definitions. → [Entity resolution](docs/en/03-entity-resolution.md)

**How it ended.** The numbers went to the bank, and the bank was satisfied with them — the
dataset did the job it was built for. It is still in use: a quarterly refresh takes about an hour,
and the bank report built on it is in its seventh version. → [Outcome](docs/en/09-outcome.md)

## The client's data stays out — on purpose

Every company name, person, product, file name, value and identifier in this repository is
**synthetic**. The case study itself is an exercise in handling a client's data: a masking map, a
machine scan against the full list of real names, and a second manual review before publishing.
→ [How this repository was anonymised](docs/en/10-data-protection.md)

## See it run in two minutes — on synthetic data

```bash
pip install openpyxl
python samples/generate_synthetic.py      # messy workbooks in every configured layout → src/data/
# third-party, not included: Chart.js 4.4.x as src/etl/chart.umd.min.js
cd src && python etl/run_etl.py           # extract → transform → load → register → JSON → dashboard.html
```

The run ends with the pipeline's own cross-checks; the dashboard picture in
[Business definitions](docs/en/06-business-definitions.md) is this run's output.

## The chapters

Short on time? Read [00](docs/en/00-at-a-glance.md) and [01](docs/en/01-the-mess.md) — fifteen minutes. If you
care how client data was kept out, add [10](docs/en/10-data-protection.md).

| # | chapter | answers | code |
|---|---|---|---|
| 00 | [At a glance](docs/en/00-at-a-glance.md) | the system on one picture, and the fourteen decisions in one line each | |
| 01 | [The mess, row by row](docs/en/01-the-mess.md) | every class of problem in the data, a synthetic example of each, and its fix | |
| 02 | [Ingestion](docs/en/02-ingestion.md) | how spreadsheets whose layout changes every year are read | [`etl/config.py`](src/etl/config.py), [`etl/extract.py`](src/etl/extract.py) |
| 03 | [Entity resolution](docs/en/03-entity-resolution.md) | how one company's twenty spellings become one partner — and who decides | [`etl/transform.py`](src/etl/transform.py), [`admin/etl_bridge.py`](src/admin/etl_bridge.py) |
| 04 | [Data model](docs/en/04-data-model.md) | two databases — what is derived, what is remembered; views; the JSON contract | [`etl/load.py`](src/etl/load.py), [`sql/views`](src/sql/views) |
| 05 | [Operator workshop](docs/en/05-operator-workshop.md) | the import wizard, the quality gate, the error-list loop with the people who type the data | [`admin/routes`](src/admin/routes) |
| 06 | [Business definitions](docs/en/06-business-definitions.md) | how a number becomes defensible in front of a bank | [`etl/export_json.py`](src/etl/export_json.py) |
| 07 | [How I worked](docs/en/07-how-i-worked.md) | the split between me and the AI, and the rules I set | |
| 08 | [Metrics](docs/en/08-metrics.md) | every number, with date and method | |
| 09 | [Outcome](docs/en/09-outcome.md) | where it stands, what is still imperfect, what I would do differently | |
| 10 | [Data protection](docs/en/10-data-protection.md) | how this repository was anonymised — and what the scans caught | [`samples/`](samples/generate_synthetic.py) |
| A | [Decision records](docs/en/adr.md) | the fifteen decisions in full | |
| B | [Glossary](docs/en/glossary.md) | the terms used here | |

The code in [`src/`](src/README.md) is a curated, masked extract of forty files, for reading — and it runs on
the synthetic data.

## What I decided

| | |
|---|---|
| **The plan** | turning "we want a dashboard / a bank report" into a pipeline with a registry, two databases, a quality gate and an operator loop |
| **Where truth lives** | source errors are fixed in the source spreadsheets by their owners; human judgements live in the operator DB; everything else is derived and disposable |
| **Business definitions** | what counts as an open, lost or live quote; which year a deal belongs to; where a multinational customer "is" |
| **What is *not* automated** | the uncertain name matches and the business definitions stay with people; analysis workstreams without a stable routine stay manual until one emerges |
| **The rules for the AI** | recompute every number from the database, never copy from the previous report; never overwrite a delivered version; no guessed data — leave it out instead |

## The numbers

*Measured 2026-10-13 on the live system; sources in [Metrics](docs/en/08-metrics.md).*

| | |
|---|---|
| In use | since March 2026, quarterly refresh (~1 hour) |
| Source | 7 years of workbooks (2020–2026), 4 of them loaded (2023–2026); 2 product groups, 8 column-layout eras |
| Code | ~7.6k lines of Python in the full system (~6.8k in this excerpt), 9 SQL views, a 28-route operator web app |
| Status vocabulary | 42 raw spellings → 10 normalised states |
| Partner names | 1,146 distinct spellings (after normalisation) → 991 canonical partners; 103 partners had 2–9 spellings |
| Operator decisions | 34 import sessions; 906 red + 17 yellow name checks decided by a person (checks across sessions, not distinct companies); 331 manual country decisions |
| Quality gate | first import per year: 104 / 167 / 26 blocking issues in the oldest years (2020–2022), 0–9 per import in 2023–2026 — almost all of them a won deal typed without its work number, caught at the gate |

---

*Code in this repository was written by Claude to my design. The plan is mine — above all the split
between what is derived and what a person decided, and the loop that sends errors back to the people
who type the data. So are the business definitions, the review of every number, and the record.*

<sub>© 2026 Krisztián Pettner. Shared for review; all rights reserved.</sub>
