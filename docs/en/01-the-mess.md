**English** · [Magyar](../hu/01-the-mess.md) · [↑ README](../../README.md)

# The mess, row by row

The source was a set of quote-tracking workbooks — one per year and product group — kept by hand
for years. They behave like **digitised paper forms**: a person fills in a row, no field is
validated, the layout is whatever made sense that year. Below is every class of problem the
pipeline had to solve, each with a **synthetic example** row (invented names and values, the same
*kind* of error) and the place in the code that handles it.

> All examples are made up. "Company 007", "Contact 03", the quote numbers and the amounts do not
> exist. The real data never left the client's machines.

## A. The same company, many names

| # | what the rows looked like | why it hurts | how it is solved | code |
|---|---|---|---|---|
| A1 | `Company 007 Kft.` · `Company 007 kft` · `COMPANY 007` | three customers instead of one: the customer count inflates, the revenue per customer splits | **normalisation**: lowercase, strip accents, punctuation → space, strip legal-form suffixes (31 patterns, from *Kft.* to *Sp. z o.o.*) → all three become `company 007` | `etl/transform.py::normalize_name`, `etl/config.py::COMPANY_SUFFIXES` |
| A2 | `Cég-Nyolc Zrt.` · `Ceg Nyolc` | accents and hyphens typed inconsistently | accent stripping + hyphen as separator (`cég-nyolc` = `ceg nyolc`) | same |
| A3 | `Company 012 Engineering` · `Company 012 Enginering` | a typo is a new company to an exact match | **similarity score** on normalised names; ≥ 0.92 merges automatically in batch runs, names shorter than 6 characters are never auto-merged | `etl/transform.py` (fuzzy merge step) |
| A4 | `Company 021 (site B, plant 2)` · `Company 021 – same as quote 153` | notes typed *into the name field* | normalisation removes the brackets but not the words → lands in the **yellow/red zone**, a person assigns it to the right partner once, the spelling is stored as an **alias** | `admin/etl_bridge.py` (staging), `admin/routes/import_wizard.py` |
| A5 | `Company 030 Group` vs `Company 030 Hungary Kft.` | is it one customer or two? a machine cannot know | **never merged automatically** below the green zone; the operator decides, the decision lives in the operator DB and survives every rebuild | `admin/routes/partners.py` (merge, aliases) |

→ The full method: [Entity resolution](03-entity-resolution.md)

## B. The layout changes every year

| # | what the rows looked like | why it hurts | how it is solved | code |
|---|---|---|---|---|
| B1 | 2023: partner in column D, value in column O; 2025: two new columns inserted before the status | a fixed column index reads the wrong field silently | a **column map per layout era** (8 eras) and a file entry per year: file → sheet → start row → map | `etl/config.py::FILE_CONFIG`, `_TG1_COLS_*`, `_TG2_COLS_*` |
| B2 | older years: no status column — five tick-box columns instead (won / lost / postponed / no quote / open) | the most important field does not exist | status **derived from the tick boxes**, with a fallback from the sent date | `etl/extract.py::_derive_tg1_status_bitmask` |
| B3 | one older year of product group 2: only a free-text feedback column (`"ordered 03.12"`, `"too expensive"`) | status hidden in prose | keyword rules (`ordered` → won; any feedback after a sent quote → lost; `cancelled` → no quote) | `etl/extract.py::_derive_tg2_status_feedback` |
| B4 | a year split over two sheets (first half / second half) | half the year missing if you read one sheet | a sheet *list* in the file entry | `etl/extract.py::extract_tg1_quotes` |
| B5 | 20 empty rows, then a forgotten test row at row 900 | reading stops too early or picks up junk | the reader stops after 20 consecutive empty rows; rows without an ID **and** a partner are skipped | `etl/extract.py::_read_sheet` |

→ [Ingestion](02-ingestion.md)

## C. Free-text status

| # | what the rows looked like | why it hurts | how it is solved | code |
|---|---|---|---|---|
| C1 | `megnyertük` · `Megnyertük ` · `megnyertuk` | the same state, three keys | exact match after trim + lowercase, then accent-stripped match | `etl/transform.py::normalize_status` |
| C2 | `>waiting to be sent<` · `>>>waiting to be sent<<<` | decoration typed into the value | both decorated forms are entries in the map | `etl/config.py::STATUS_MAP` |
| C3 | a status nobody has seen before | NULL status = the quote vanishes from every funnel | the import wizard shows a **dedicated step for unknown statuses**; the operator maps it once, it is stored in the status dictionary and applied from then on | `admin/routes/status_dict.py`, `normalize_status` (since Oct 2026 — see [Outcome](09-outcome.md)) |

42 raw spellings map to 10 states, each with explicit *open / won / lost* flags.

## D. Rows that are not what they look like

| # | what the rows looked like | why it hurts | how it is solved | code |
|---|---|---|---|---|
| D1 | quote `Q2-26-118` on four rows: one header, three rows with status `[order line item]` | counted as four quotes, value counted four times | line items are split off by their status marker and **summed into the quote header** | `etl/extract.py::extract_tg2_quotes`, `etl/transform.py::transform_tg2_quotes` |
| D2 | older year: the line items have **no quote ID** — just the rows under the header | they look like empty-ID junk | continuation rows are attached to the last header (forward fill) | `etl/extract.py::extract_tg2_quotes` (older-layout branch) |
| D3 | the same quote ID in two years' files (carried over in January) | double counting across years | dedup by quote ID, the **later year wins** | `etl/transform.py::transform_all` (step 4) |
| D4 | a request with a value of 1.9 M, status *no quote made* | a request we never quoted inflates the "quoted value" | **quoted value excludes no-quote rows** by definition; the request still counts as demand | `etl/export_json.py` (funnel), [Business definitions](06-business-definitions.md) |
| D5 | a quote from three years ago, still "open" | never-closed quotes inflate the pipeline | **live pipeline = quoted within the last 12 months**; older open quotes are listed as *stale*, to be closed in the source | `sql/views/04_pipeline.sql` |

## E. Values and identifiers

| # | what the rows looked like | why it hurts | how it is solved | code |
|---|---|---|---|---|
| E1 | `#REF!` · `#N/A` · `-` · `Missing, please fill in!` | spreadsheet errors read as text values | one set of **missing-value markers** → NULL everywhere | `etl/config.py::MISSING_MARKERS`, `transform.py::_clean_value` |
| E2 | value `41 800 000` in a EUR column, on a mid-size order | the unit was HUF, typed into the EUR column | flagged in the quality review as an outlier, **fixed in the source** by its owner — not in the DB | (process — see [Operator workshop](05-operator-workshop.md)) |
| E3 | work number `26902`, `26902/1`, `W90126/A`, `2690` | the work number links a won quote to the order register; formats differ per product group, sub-numbers are appended | one regex per product group: year + serial + optional part; anything else is logged as an anomaly | `etl/transform.py::parse_work_number` |
| E4 | quote requested in 2025, work number from 2026 | which year did we "win" it? | flagged as **cross-year**; the funnel uses the request year, the order register its own year — never mixed | `transform.py::detect_crossyear`, [Business definitions](06-business-definitions.md) |
| E5 | status *won*, no work number | the deal cannot be found in the order register | **blocking issue** in the import wizard — the import does not proceed until the source is fixed or the operator overrides it with a written reason | `admin/etl_bridge.py::collect_blocking_issues` |
| E6 | request date empty; or sent 140 days after the request | reaction-time and same-period figures go wrong | warnings in the quality list (missing date, reaction > 90 days) | `transform.py::_collect_anomalies` |

## F. Countries

| # | what the rows looked like | why it hurts | how it is solved | code |
|---|---|---|---|---|
| F1 | country never recorded for many partners (some years had no partner sheet at all) | no domestic/foreign split — the core question of the bank report | a **country resolver** with six ranked strategies — earlier operator decisions, partner-ID cross-reference, one year's partner sheet, the other product group's partner list, the domestic flag, the legal-form suffix — each with a method and confidence label; what stays unresolved goes to a person as a CSV and comes back as manual decisions | `scripts/resolve_countries.py` |
| F2 | `Lengyel` · `Lengyelország`; `Cseh Köztársaság` · `Csehország` | the same country, two keys | a country map to ISO codes and regions | `etl/config.py::COUNTRY_NAME_MAP` |
| F3 | flag *foreign*, country *Hungary* | the flag and the name contradict each other | **domestic/foreign is always derived from the country name**; the flag is only a fallback (a bug here was found and fixed in Oct 2026) | `etl/transform.py::transform_tg1_quotes` |
| F4 | `Company 041 Kft.` — registered locally, but every contact, order and invoice goes to the group's plant abroad | registry country ≠ market reality | rule: **country = the entity we actually transact with**; a person decides, the decision is stored and overrides everything else | `transform.py::load_country_overrides` |

## G. The second source: the order register

| # | what the rows looked like | why it hurts | how it is solved | code |
|---|---|---|---|---|
| G1 | one order on three rows: `26902/1`, `26902/2`, `26902/3` | three orders instead of one | sub-numbers stripped, amounts summed per order | `scripts/extract_work_orders.py` |
| G2 | a two-year project appears in both years' registers, each with that year's share | looks like a duplicate | **not deduplicated on purpose**: each year carries its own accrued share | same |
| G3 | an internal order: product group 2 made for a product group 1 job | the revenue would be counted twice | own-production orders excluded at order level | same |
| G4 | the same work number on two different customers | a typo in the key | reported as a collision on the register's own error list | same |
| G5 | an amount in EUR and, next to it, an invoiced amount in HUF | two currencies for one order — which one counts? | **the EUR contract price is the source of truth**; the EUR invoiced amount only fills a gap; the HUF column is deliberately never converted or used | same |

## Plan vs built

| planned | built |
|---|---|
| "clean the data once" | a repeatable set of rules + an operator loop, because the same errors keep being typed |
| automatic merge of all similar names | automatic only in the green zone; everything uncertain is decided by a person |
| fix bad values in the database | fix them in the source — a DB patch would be lost on the next rebuild |
