# The code — a curated extract

**English** · magyarul lent

This folder holds the core of the system: forty files plus the synthetic-data generator, the parts the chapters talk
about. It is a **reading set**. The ETL does run on the synthetic sample data (`samples/`), but the
real deployment depends on the client's workbooks and operator database, which are not here.

Code comments and user-facing texts are partly in Hungarian, as written during the project. All
company names, file names, product terms and identifiers are replaced by synthetic ones; the two
product lines are `TG1` / `TG2` (product group 1 / 2). Replacements were applied to this copy only.

| chapter | read |
|---|---|
| [The mess, row by row](../docs/en/01-the-mess.md) — every problem class → its handler | see the `code` column of each table |
| [Ingestion](../docs/en/02-ingestion.md) — the registry, column maps, status vocabulary, missing markers | `etl/config.py` |
| — the generic reader, tick-box / free-text status recovery, line items | `etl/extract.py` |
| [Entity resolution](../docs/en/03-entity-resolution.md) — normalisation, batch fuzzy merge, status normalisation, work numbers, country overrides, anomalies | `etl/transform.py` |
| — the operator path: staging, zones, quality gate | `admin/etl_bridge.py` |
| — partner master, aliases, merge | `admin/routes/partners.py`, `admin/db/schema.sql` |
| [Data model](../docs/en/04-data-model.md) — schema, incremental load, alias dedupe | `etl/load.py` |
| — the reporting layer | `sql/views/01_…09_*.sql` |
| — the JSON contract v2 | `etl/export_json.py` |
| — the page (template + client-side render) | `etl/generate_dashboard.py` |
| — orchestration + run-time cross-checks | `etl/run_etl.py` |
| [Operator workshop](../docs/en/05-operator-workshop.md) — the wizard | `admin/routes/import_wizard.py`, `admin/templates/import/` |
| — status dictionary | `admin/routes/status_dict.py` |
| — order register: accrual, reconciliation, error list | `scripts/extract_work_orders.py` |
| [Entity resolution → country](../docs/en/01-the-mess.md#f-countries) — six-strategy resolver | `scripts/resolve_countries.py` |
| [Data protection](../docs/en/10-data-protection.md) — the synthetic dataset | `samples/generate_synthetic.py` |

**Not included:** the vendored Chart.js bundle (third-party; the page generator expects it at
`etl/chart.umd.min.js`), a report-formatting utility, a diagnostic worksheet generator, the sync
scripts, the databases and every data file.

---

## A kód — kurált kivonat

Ez a mappa a rendszer magját tartalmazza: negyven fájlt és a szintetikusadat-generátort, azokat a részeket, amelyekről a
fejezetek szólnak. **Olvasásra** készült. Az ETL a szintetikus mintaadaton (`samples/`) lefut, de a
valódi üzem a megbízó munkafüzeteire és operátori adatbázisára épül, amelyek nincsenek itt.

A kódkommentek és a felhasználói szövegek részben magyarul vannak, ahogy a projekt alatt íródtak.
Minden cégnév, fájlnév, termék-kifejezés és azonosító szintetikusra cserélve; a két termékvonal
`TG1` / `TG2` (1. / 2. termékcsoport). A cserék csak ezen a másolaton történtek.

A fejezet → fájl megfeleltetés a fenti táblában; a magyar fejezetek: [docs/hu/](../docs/hu/).

**Nincs benne:** a beágyazott Chart.js csomag (harmadik fél; a lapgenerátor az
`etl/chart.umd.min.js` helyen várja), egy riport-formázó segédszkript, egy diagnosztikai
munkalap-generátor, a szinkron-szkriptek, az adatbázisok és minden adatfájl.
