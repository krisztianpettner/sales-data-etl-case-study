**English** · [Magyar](../hu/glossary.md) · [↑ README](../../README.md)

# Glossary

| term | meaning here |
|---|---|
| **accrual** | a multi-year order is counted in each register year with the share booked to that year — never deduplicated across years |
| **alias** | one spelling of a partner's name as it was typed in a source, stored against the canonical partner |
| **analytics DB** | `dashboard.db` — fully derived from the workbooks and the operator DB; disposable |
| **blocking issue** | a quality-gate finding that stops an import until fixed or overridden with a written reason |
| **canonical partner** | the one record (`PM-xxxx`) that all spellings of a company resolve to |
| **closed, no response** | a sent quote with no answer for 90–120 days, closed after the fact; not counted as lost |
| **column map** | the config entry that says which column holds which field in one layout era |
| **conversion** | won value ÷ quoted value |
| **cross-year** | a deal requested in one year and won (work number) in another |
| **error list** | the per-year list of quality-gate findings handed to the spreadsheet owners (Hungarian: *hibajegyzék*) |
| **funnel** | requests → quoted → won / lost / postponed / open, by request year |
| **layout era** | a span of years in which a workbook kept the same column layout |
| **line item** | one position of a multi-position quote; its value is summed into the quote |
| **live pipeline** | quoted, requested within 12 months of the latest request in the data |
| **normalisation** | lowercase, strip accents, punctuation to space, strip legal-form suffix — the first step of name matching |
| **operator** | the person running the import wizard and making the judgement calls |
| **operator DB** | `admin.db` — persistent store of every human decision |
| **order register** | the yearly workbook of contracted orders; the source of realised revenue |
| **product group 1 / 2** | the client's two product lines (TG1 / TG2 in code); what they are does not matter to the method |
| **quoted value** | sum of quote values excluding requests that were never quoted |
| **realised revenue** | value from the order register by register year, with accrual |
| **request year** | the year the request for quotation arrived — the funnel's year basis |
| **stale quote** | an open quote older than the live-pipeline window; to be closed in the source |
| **status dictionary** | operator-added raw statuses and their normalised state |
| **third division (S)** | a third line of business that appears only in the order register (four-digit work numbers, no quote funnel); reported on its own row |
| **win rate** | won ÷ (won + lost), by count |
| **work number** | the job number issued when a quote is won; the key between quotes and the order register |
| **zone** | green (≥ 0.95, automatic), yellow (0.85–0.95), red (< 0.85) — the similarity bands of name matching |
