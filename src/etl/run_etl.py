#!/usr/bin/env python3
"""
Sales Dashboard — ETL runner.

Reads raw Excel files → normalizes → writes SQLite database.
Fully re-runnable: drops and recreates all tables each time.

Usage:
    python run_etl.py
"""
import logging
import sqlite3
import sys
import time
from pathlib import Path

# Ensure etl/ is on the path so config/extract/transform/load can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DB_PATH, EXCEL_FILES, PROJECT_ROOT
from extract import extract_all
from transform import transform_all
from load import load_all
from export_json import export as export_json
from generate_dashboard import generate as generate_html

# rendelesi_regiszter (order register) extractor lives in scripts/ — part of the chain since 2026-10-12
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
try:
    from extract_work_orders import run as load_work_orders
except Exception as _e:  # pragma: no cover
    load_work_orders = None
    _wo_import_error = _e

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("etl")


def verify(db_path):
    """Run verification queries and print summary."""
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    print("\n" + "=" * 70)
    print("  VERIFICATION")
    print("=" * 70)

    # Partner count
    cur.execute("SELECT COUNT(*) FROM partners")
    print(f"\n  Partners:      {cur.fetchone()[0]}")

    # Partner source breakdown
    cur.execute("SELECT source, COUNT(*) FROM partners GROUP BY source ORDER BY source")
    for source, cnt in cur.fetchall():
        print(f"    {source}: {cnt}")

    # Quote count by product line + year
    print(f"\n  Quotes by product line & year:")
    cur.execute("""
        SELECT product_line, year, COUNT(*),
               COALESCE(SUM(total_value_eur), 0)
        FROM quotes
        GROUP BY product_line, year
        ORDER BY product_line, year
    """)
    for pl, yr, cnt, val in cur.fetchall():
        print(f"    {pl} {yr}: {cnt:>4} quotes, {val:>14,.0f} EUR total")

    # Status breakdown
    print(f"\n  Status breakdown:")
    cur.execute("""
        SELECT product_line, status, COUNT(*)
        FROM quotes
        GROUP BY product_line, status
        ORDER BY product_line, status
    """)
    for pl, st, cnt in cur.fetchall():
        print(f"    {pl} / {st or '(NULL)'}: {cnt}")

    # Pipeline (élő = 12 hónapon belüli QUOTED; elavult = régebbi nyitott)
    cur.execute("SELECT SUM(is_live=1 AND status='QUOTED'), COALESCE(SUM(CASE WHEN is_live=1 AND status='QUOTED' THEN total_value_eur END),0), "
                "SUM(is_live=0), COALESCE(SUM(CASE WHEN is_live=0 THEN total_value_eur END),0) FROM v_pipeline")
    pcnt, pval, scnt, sval = cur.fetchone()
    print(f"\n  Live pipeline (12 hó, QUOTED): {pcnt or 0} quotes, {pval:,.0f} EUR  |  elavult nyitott: {scnt or 0} db, {sval:,.0f} EUR")
    if cur.execute("SELECT name FROM sqlite_master WHERE name='v_work_orders_eur'").fetchone():
        print("  rendelesi_regiszter (realizált, EUR):")
        for pl, yr, eur in cur.execute("SELECT product_line, year, eur_sot FROM v_work_orders_eur ORDER BY year, product_line"):
            print(f"    {pl} {yr}: {eur:>12,.0f}")

    # Win rates
    print(f"\n  Win rates (YTD comparison):")
    cur.execute("SELECT product_line, year, total_quotes, won_count, win_rate_pct FROM v_ytd_comparison")
    for pl, yr, tot, won, wr in cur.fetchall():
        print(f"    {pl} {yr}: {won}/{tot} quotes → {wr or 0:.1f}% win rate")

    # Data quality
    print(f"\n  Data quality:")
    cur.execute("SELECT COUNT(*) FROM quotes WHERE partner_id IS NULL")
    print(f"    Quotes with unmatched partner: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM quotes WHERE status IS NULL")
    print(f"    Quotes with unknown status:    {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM quotes WHERE request_date IS NULL")
    print(f"    Quotes with missing req. date: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM partners WHERE country IS NULL")
    print(f"    Partners with missing country: {cur.fetchone()[0]}")

    # Cross-check against a figure pinned from the real data (production pins a known count;
    # the pinned value is not part of this case-study copy)
    cur.execute("SELECT COUNT(*) FROM quotes WHERE product_line='TG1' AND year=2025 AND status='WON'")
    tg1_25_won = cur.fetchone()[0]
    expected = None  # pinned in production
    check = "not pinned" if expected is None else "OK" if tg1_25_won == expected else f"MISMATCH (expected {expected})"
    print(f"\n  Cross-check: TG1 2025 WON = {tg1_25_won} [{check}]")

    # Quote lines
    cur.execute("SELECT COUNT(*) FROM quote_lines")
    print(f"  TG2 quote lines: {cur.fetchone()[0]}")

    print("\n" + "=" * 70)
    conn.close()


def main():
    t0 = time.time()

    # Check source files exist
    for key, path in EXCEL_FILES.items():
        if not path.exists():
            log.error("Missing source file: %s → %s", key, path)
            sys.exit(1)
    log.info("All source files found.")

    # Extract
    log.info("─── EXTRACT ───")
    raw_data = extract_all()

    # Transform
    log.info("─── TRANSFORM ───")
    transformed = transform_all(raw_data)

    # Load
    log.info("─── LOAD ───")
    db_path = load_all(transformed)

    # Order register (rendelesi_regiszter) → work_orders + hibalista. Needs the quotes already
    # loaded (has_quote / quote_status are computed against the current quotes).
    log.info("─── RENDELESI_REGISZTER (work_orders) ───")
    if load_work_orders is None:
        log.warning("work_orders extractor import failed (%s) — register layer skipped", _wo_import_error)
    else:
        try:
            wo = load_work_orders()
            log.info("work_orders loaded: %d rows, TG1 %.0f / TG2 %.0f / S %.0f EUR, hibalista %d → %s",
                     wo["rows"], wo["tg1_eur"], wo["tg2_eur"], wo["s_eur"], wo["hibalista"], wo["hibalista_xlsx"])
        except FileNotFoundError as e:
            log.warning("register source missing (%s) — register layer skipped", e)

    # Export JSON
    log.info("─── EXPORT JSON ───")
    json_path = export_json()

    # Generate HTML dashboard
    log.info("─── GENERATE DASHBOARD ───")
    html_out = PROJECT_ROOT / "dashboard.html"
    html = generate_html()
    html_out.write_text(html, encoding="utf-8")
    log.info("Dashboard written to %s (%d KB)", html_out, html_out.stat().st_size // 1024)

    elapsed = time.time() - t0
    log.info("ETL complete in %.1fs → %s", elapsed, db_path)

    # Verify
    verify(db_path)


if __name__ == "__main__":
    main()
