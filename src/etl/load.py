"""
Load — create SQLite schema and insert normalized data.
"""
import logging
import sqlite3
from config import DB_PATH, SQL_DIR

log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
#  Schema DDL
# ══════════════════════════════════════════════════════════════════════════════

SCHEMA_SQL = """
-- Partners
CREATE TABLE IF NOT EXISTS partners (
    partner_id          TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    name_normalized     TEXT,
    official_name       TEXT,
    tax_id              TEXT,
    country             TEXT,
    is_domestic         INTEGER,
    partner_type        TEXT,
    industry            TEXT,
    teaor_code          TEXT,
    first_contact_date  TEXT,
    source              TEXT
);

-- Quotes
CREATE TABLE IF NOT EXISTS quotes (
    quote_id            TEXT PRIMARY KEY,
    product_line        TEXT NOT NULL,
    year                INTEGER NOT NULL,
    partner_id          TEXT REFERENCES partners(partner_id),
    partner_name_raw    TEXT,
    subject             TEXT,
    handler_name        TEXT,
    handler_email       TEXT,
    request_date        TEXT,
    deadline_date       TEXT,
    sent_date           TEXT,
    close_date          TEXT,
    status_raw          TEXT,
    status              TEXT,
    registry_number     TEXT,
    revision            TEXT,
    total_value_eur     REAL,
    work_number         TEXT,
    work_number_year    INTEGER,
    work_number_part    TEXT,
    is_crossyear        INTEGER,
    work_number_anomaly TEXT,
    country             TEXT,
    is_domestic         INTEGER,
    loss_reason         TEXT,
    reaction_days       REAL
);

-- TG2 quote line items
CREATE TABLE IF NOT EXISTS quote_lines (
    line_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id            TEXT NOT NULL REFERENCES quotes(quote_id),
    position            INTEGER,
    quantity            INTEGER,
    unit_price_eur      REAL,
    line_value_eur      REAL,
    product_type        TEXT,
    material            TEXT,
    size_param      REAL,
    status_raw          TEXT
);

-- Status normalization mapping
CREATE TABLE IF NOT EXISTS status_map (
    raw_status          TEXT PRIMARY KEY,
    normalized_status   TEXT NOT NULL,
    is_open             INTEGER NOT NULL DEFAULT 0,
    is_won              INTEGER NOT NULL DEFAULT 0,
    is_lost             INTEGER NOT NULL DEFAULT 0
);

-- Partner name aliases (all raw name variants per partner)
CREATE TABLE IF NOT EXISTS partner_aliases (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id          TEXT NOT NULL REFERENCES partners(partner_id),
    alias_name          TEXT NOT NULL,
    name_normalized     TEXT NOT NULL
);

-- Data anomalies log
CREATE TABLE IF NOT EXISTS anomalies (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    type                TEXT NOT NULL,
    quote_id            TEXT,
    detail              TEXT NOT NULL
);
"""

INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_quotes_partner     ON quotes(partner_id);
CREATE INDEX IF NOT EXISTS idx_quotes_status      ON quotes(status);
CREATE INDEX IF NOT EXISTS idx_quotes_product     ON quotes(product_line);
CREATE INDEX IF NOT EXISTS idx_quotes_year        ON quotes(year);
CREATE INDEX IF NOT EXISTS idx_quotes_req_date    ON quotes(request_date);
CREATE INDEX IF NOT EXISTS idx_quotes_pl_year     ON quotes(product_line, year);
CREATE INDEX IF NOT EXISTS idx_qlines_quote       ON quote_lines(quote_id);
CREATE INDEX IF NOT EXISTS idx_partners_norm      ON partners(name_normalized);
"""

def _load_view_sql_files(conn):
    """Load SQL view definitions from sql/views/*.sql files in order."""
    sql_files = sorted(SQL_DIR.glob("*.sql"))
    if not sql_files:
        log.warning("No SQL view files found in %s", SQL_DIR)
        return
    for f in sql_files:
        sql = f.read_text(encoding="utf-8")
        conn.executescript(sql)
        log.info("  View loaded: %s", f.name)
    log.info("Loaded %d SQL view files", len(sql_files))


# ══════════════════════════════════════════════════════════════════════════════
#  Load functions
# ══════════════════════════════════════════════════════════════════════════════

def _drop_all(conn):
    """Drop all tables and views for a clean reload."""
    conn.executescript("""
        DROP VIEW  IF EXISTS v_kpi_snapshot;
        DROP VIEW  IF EXISTS v_data_quality;
        DROP VIEW  IF EXISTS v_performance_scorecard;
        DROP VIEW  IF EXISTS v_industry_summary;
        DROP VIEW  IF EXISTS v_market_summary;
        DROP VIEW  IF EXISTS v_loss_reasons;
        DROP VIEW  IF EXISTS v_ytd_comparison;
        DROP VIEW  IF EXISTS v_monthly_summary;
        DROP VIEW  IF EXISTS v_pipeline;
        DROP TABLE IF EXISTS anomalies;
        DROP TABLE IF EXISTS partner_aliases;
        DROP TABLE IF EXISTS quote_lines;
        DROP TABLE IF EXISTS quotes;
        DROP TABLE IF EXISTS status_map;
        DROP TABLE IF EXISTS partners;
    """)


def _insert_partners(conn, partners):
    conn.executemany("""
        INSERT OR REPLACE INTO partners
            (partner_id, name, name_normalized, official_name, tax_id,
             country, is_domestic, partner_type, industry, teaor_code,
             first_contact_date, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (p["partner_id"], p["name"], p["name_normalized"], p["official_name"],
         p["tax_id"], p["country"], p["is_domestic"], p["partner_type"],
         p["industry"], p["teaor_code"], p["first_contact_date"], p["source"])
        for p in partners
    ])
    log.info("Loaded %d partners", len(partners))


def _insert_quotes(conn, quotes):
    conn.executemany("""
        INSERT OR REPLACE INTO quotes
            (quote_id, product_line, year, partner_id, partner_name_raw,
             subject, handler_name, handler_email, request_date, deadline_date,
             sent_date, close_date, status_raw, status, registry_number,
             revision, total_value_eur, work_number, work_number_year,
             work_number_part, is_crossyear, work_number_anomaly,
             country, is_domestic, loss_reason, reaction_days)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (q["quote_id"], q["product_line"], q["year"], q["partner_id"],
         q["partner_name_raw"], q["subject"], q["handler_name"], q["handler_email"],
         q["request_date"], q["deadline_date"], q["sent_date"], q["close_date"],
         q["status_raw"], q["status"], q["registry_number"], q["revision"],
         q["total_value_eur"], q["work_number"], q.get("work_number_year"),
         q.get("work_number_part"), q.get("is_crossyear"), q.get("work_number_anomaly"),
         q["country"], q["is_domestic"], q["loss_reason"], q["reaction_days"])
        for q in quotes
    ])
    log.info("Loaded %d quotes", len(quotes))


def _insert_partner_aliases(conn, aliases):
    conn.executemany("""
        INSERT OR IGNORE INTO partner_aliases (partner_id, alias_name, name_normalized)
        VALUES (?, ?, ?)
    """, [(a["partner_id"], a["alias_name"], a["name_normalized"]) for a in aliases])
    log.info("Loaded %d partner aliases", len(aliases))


def _insert_anomalies(conn, anomalies):
    conn.executemany("""
        INSERT INTO anomalies (type, quote_id, detail)
        VALUES (?, ?, ?)
    """, [(a["type"], a.get("quote_id"), a["detail"]) for a in anomalies])
    log.info("Loaded %d anomalies", len(anomalies))


def _insert_quote_lines(conn, lines):
    conn.executemany("""
        INSERT INTO quote_lines
            (quote_id, position, quantity, unit_price_eur, line_value_eur,
             product_type, material, size_param, status_raw)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (l["quote_id"], l["position"], l["quantity"], l["unit_price_eur"],
         l["line_value_eur"], l["product_type"], l["material"],
         l["size_param"], l["status_raw"])
        for l in lines
    ])
    log.info("Loaded %d quote lines", len(lines))


def _insert_status_map(conn, rows):
    conn.executemany("""
        INSERT OR REPLACE INTO status_map
            (raw_status, normalized_status, is_open, is_won, is_lost)
        VALUES (?, ?, ?, ?, ?)
    """, [
        (r["raw_status"], r["normalized_status"], r["is_open"], r["is_won"], r["is_lost"])
        for r in rows
    ])
    log.info("Loaded %d status map entries", len(rows))


# ══════════════════════════════════════════════════════════════════════════════
#  Main load orchestrator
# ══════════════════════════════════════════════════════════════════════════════

def _detect_pl_years(transformed):
    """Detect which (product_line, year) combinations are in this import."""
    pl_years = set()
    for q in transformed.get("quotes", []):
        pl_years.add((q["product_line"], q["year"]))
    return pl_years


def _drop_views(conn):
    """Drop all views (they need to be recreated after schema changes)."""
    conn.executescript("""
        DROP VIEW  IF EXISTS v_kpi_snapshot;
        DROP VIEW  IF EXISTS v_data_quality;
        DROP VIEW  IF EXISTS v_performance_scorecard;
        DROP VIEW  IF EXISTS v_industry_summary;
        DROP VIEW  IF EXISTS v_market_summary;
        DROP VIEW  IF EXISTS v_loss_reasons;
        DROP VIEW  IF EXISTS v_ytd_comparison;
        DROP VIEW  IF EXISTS v_monthly_summary;
        DROP VIEW  IF EXISTS v_pipeline;
    """)


def _delete_pl_years(conn, pl_years):
    """Delete existing data for the given (product_line, year) combinations."""
    for pl, year in pl_years:
        # Delete quote_lines for these quotes
        conn.execute("""
            DELETE FROM quote_lines WHERE quote_id IN (
                SELECT quote_id FROM quotes WHERE product_line = ? AND year = ?
            )
        """, (pl, year))
        # Delete quotes
        conn.execute(
            "DELETE FROM quotes WHERE product_line = ? AND year = ?",
            (pl, year),
        )
        log.info("Cleared existing data for %s %d", pl, year)


def load_all(transformed):
    """Load data incrementally — only replace the product_line+year combos in this import."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # executescript() COMMITs implicitly, so rollback() alone cannot undo the
    # per-year DELETE below if a later step fails: keep a snapshot and restore it
    snapshot = sqlite3.connect(":memory:")
    conn.backup(snapshot)

    try:
        # Ensure schema exists
        conn.executescript(SCHEMA_SQL)
        # partner_aliases had no UNIQUE key, so INSERT OR IGNORE re-added every
        # alias on each run: dedupe once, then enforce uniqueness
        conn.executescript("""
            DELETE FROM partner_aliases WHERE id NOT IN (
                SELECT MIN(id) FROM partner_aliases
                GROUP BY partner_id, alias_name, name_normalized);
            CREATE UNIQUE INDEX IF NOT EXISTS ux_partner_aliases
                ON partner_aliases(partner_id, alias_name, name_normalized);
        """)

        # Detect which PL+year combos are being imported
        pl_years = _detect_pl_years(transformed)
        log.info("Incremental load for: %s", pl_years)

        # Delete only the affected PL+year data
        _delete_pl_years(conn, pl_years)

        # Clear anomalies (rebuilt each run)
        conn.execute("DELETE FROM anomalies")

        # Drop and recreate views
        _drop_views(conn)

        # Insert new data
        _insert_partners(conn, transformed["partners"])
        _insert_quotes(conn, transformed["quotes"])
        _insert_quote_lines(conn, transformed["quote_lines"])
        _insert_status_map(conn, transformed["status_map"])
        _insert_partner_aliases(conn, transformed.get("partner_aliases", []))
        _insert_anomalies(conn, transformed.get("anomalies", []))
        conn.executescript(INDEXES_SQL)
        _load_view_sql_files(conn)
        conn.commit()
        log.info("Database written to %s", DB_PATH)
    except Exception:
        conn.rollback()
        snapshot.backup(conn)
        log.error("Load failed — database restored to its state before this load")
        raise
    finally:
        snapshot.close()
        conn.close()

    return DB_PATH
