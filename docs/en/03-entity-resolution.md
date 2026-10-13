**English** · [Magyar](../hu/03-entity-resolution.md) · [↑ README](../../README.md)

# Entity resolution — one company, twenty spellings

## Why this is the hard part

Nobody types a customer's name the same way twice. Over the years one customer collected up to
**nine** different spellings. Every downstream number — customers per year, new vs returning,
revenue per country, win rate per partner — is only as good as the answer to *"are these two rows
the same company?"*

The two possible mistakes are not equal:

| mistake | effect | detectability |
|---|---|---|
| **missed merge** (one company counted as two) | customer count too high, "new partner" inflated | visible: two similar names side by side in a list |
| **wrong merge** (two companies counted as one) | revenue moved silently from one customer to another | invisible in every aggregate |

So the design principle is: **automate the cheap mistake, leave the expensive one to a person.**

## The pipeline

```mermaid
flowchart TB
    RAW[raw name from the sheet<br/>'Cég-Nyolc Zrt. (site B)'] --> N[normalise<br/>lowercase · strip accents · punctuation → space<br/>strip legal-form suffix]
    N --> K['ceg nyolc site b']
    K --> S[similarity vs every partner<br/>and every stored alias<br/>length-blocked · a known alias scores 1.0]
    S --> Z{score}
    Z -->|≥ 0.95 green| AUTO[accepted automatically]
    Z -->|0.85–0.95 yellow| H[operator decides]
    Z -->|< 0.85 red| H
    H -->|accept| P
    H -->|reassign to another partner| AL[new alias stored]
    H -->|new partner| NEW[new PM-xxxx]
    AUTO --> P[canonical partner<br/>PM-0123]
    AL --> P
    NEW --> P
```

### 1. Normalisation (`etl/transform.py::normalize_name`)

Lowercase → strip accents (Unicode NFKD) → punctuation **including hyphens** becomes a space →
collapse whitespace → strip a legal-form suffix anchored at the end (31 patterns: *Kft., Zrt., Bt.,
GmbH, AG, s.r.o., Sp. z o.o., B.V., Ltd., Inc.* …) → collapse whitespace again.

| raw (synthetic) | normalised |
|---|---|
| `Cég 007 Kft.` | `ceg 007` |
| `CÉG 007 kft` | `ceg 007` |
| `Ceg-007` | `ceg 007` |
| `Company 044 Sp. z o.o.` | `company 044` |

Normalisation alone resolves the bulk: in the operator DB, 1,146 distinct normalised spellings
belong to 991 partners — the raw spellings behind them are many more.

### 2. Candidates and score

Similarity is `difflib.SequenceMatcher` ratio on the normalised strings — deliberately simple and
explainable to an operator ("94% similar"). Two guards keep it cheap and safe:

- **length blocking**: candidates whose length differs by more than 40% (wizard) / 15% (batch) are
  not compared at all;
- **short names are never auto-merged** in batch runs (< 6 characters) — `abc` vs `abd` is 67% the
  same string and 0% the same company.

### 3. Zones instead of one threshold

| zone | score | what happens | measured (34 import sessions, Mar–Jun 2026) |
|---|---|---|---|
| green | ≥ 0.95 | accepted automatically | 6,131 name checks |
| yellow | 0.85–0.95 | operator decides | 17 (5 accepted · 10 reassigned · 2 new) |
| red | < 0.85 | operator decides | 906 (79 reassigned to an existing partner · 827 new partners) |

The red list also **compares red names with each other** and shows a "similar to …" hint above
0.6 — two new spellings of the same unknown company arriving in the same file are caught before
they become two partners (`admin/routes/import_wizard.py`).

*The counts are name checks across all sessions — the same name is checked again in every
session that contains it; they measure operator workload, not distinct companies.*

### 4. The decision is stored, not re-made

Every decision lands in the **operator DB** (`admin/db/schema.sql`):

| table | holds |
|---|---|
| `partner_master` | the canonical partner (`PM-0001` …), display name, country, notes |
| `partner_aliases` | every spelling ever seen → its partner, with the source (`extract` / `manual` / `fuzzy_merge`); unique per partner + normalised name |
| `partner_merges` | when two canonical partners turn out to be one: who was kept, who was merged, why |

Next quarter the same misspelling is an exact alias hit — no question asked. The first import
needed hundreds of decisions; later imports need a handful.

### 5. Merging two partners after the fact

`admin/routes/partners.py` (merge): the aliases of the merged partner move to the kept one, its
display name becomes an alias too, the merge is logged with a reason, then the merged record is
deleted. The quotes follow automatically on the next ETL run, because they are linked through the
aliases — nothing in the derived DB is edited by hand.

## The batch path

The standalone ETL (`run_etl.py`) has its own, stricter automatic step for runs without an
operator: similarity ≥ 0.92, names of at least 6 characters, length difference ≤ 15%; merged keys
become redirect aliases. The operator DB's decisions are applied on top. *(Two ID schemes — batch
`P-` and wizard `PM-` — still coexist in the derived DB; see [Outcome](09-outcome.md).)*

## Country: the second identity question

"Which country is this customer?" is the same kind of problem — and the bank report's main
split is domestic vs foreign. The rule is **the entity we actually transact with**, not the
registry entry or the group HQ. A six-strategy resolver proposes, each with a method and a
confidence label; 331 decisions were made by a person and override everything else. Details:
[The mess, F1–F4](01-the-mess.md#f-countries).

## Plan vs built

| planned | built | note |
|---|---|---|
| merge similar names automatically | automatic only above 0.95; a person decides the rest | a wrong merge is invisible in every total |
| a cleaned partner list | a partner master **plus** every spelling as an alias | the list stays correct when the same typo comes back next year |
| one matcher | two paths (batch + wizard) with different thresholds | the batch path needs no operator; the wizard path is where judgement happens |
| enrich partners from company registers (industry, size) | country only | the rest is shelved — no guessed data |
