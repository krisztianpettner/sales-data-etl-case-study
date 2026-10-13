"""
Country Resolution Script — auto-resolve + manual workflow for missing country data.

Stores all resolutions in admin.db `country_resolutions` table.
Manual entries survive re-runs (only system-resolved rows get refreshed).

Usage:
    python scripts/resolve_countries.py          # run auto-resolution
    python scripts/resolve_countries.py --status  # show current resolution status
"""

import sys
import os
import re
import sqlite3
import csv
import logging
from pathlib import Path
from datetime import datetime

# ── Path setup ────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
ETL_DIR = PROJECT_ROOT / "etl"
DATA_DIR = PROJECT_ROOT / "data"
ADMIN_DB = PROJECT_ROOT / "admin" / "admin.db"

sys.path.insert(0, str(ETL_DIR))
from config import FILE_CONFIG, MISSING_MARKERS, COUNTRY_NAME_MAP
from extract import extract_tg1_quotes, extract_tg2_quotes, extract_partners
from transform import normalize_name

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  Force FILE_CONFIG to use data/ folder (real data, not mock)
# ══════════════════════════════════════════════════════════════════════════════

def _force_data_dir():
    """Override FILE_CONFIG paths to prefer data/ subfolder."""
    changed = 0
    for key, cfg in FILE_CONFIG.items():
        alt = DATA_DIR / cfg["file"].name
        if alt.exists():
            cfg["file"] = alt
            changed += 1
    log.info(f"Redirected {changed}/{len(FILE_CONFIG)} files to data/ folder")

_force_data_dir()


# ══════════════════════════════════════════════════════════════════════════════
#  Schema
# ══════════════════════════════════════════════════════════════════════════════

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS country_resolutions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_name_raw      TEXT NOT NULL,
    partner_name_normalized TEXT NOT NULL UNIQUE,
    resolved_country      TEXT,
    is_domestic           INTEGER,
    resolution_method     TEXT NOT NULL,
    source_detail         TEXT,
    resolved_at           TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_by           TEXT NOT NULL DEFAULT 'system',
    confidence            TEXT NOT NULL DEFAULT 'high'
);

CREATE INDEX IF NOT EXISTS idx_cr_normalized ON country_resolutions(partner_name_normalized);
CREATE INDEX IF NOT EXISTS idx_cr_method ON country_resolutions(resolution_method);
CREATE INDEX IF NOT EXISTS idx_cr_country ON country_resolutions(resolved_country);
"""


# ══════════════════════════════════════════════════════════════════════════════
#  Suffix → country mapping (unambiguous only)
# ══════════════════════════════════════════════════════════════════════════════

SUFFIX_COUNTRY = [
    # Hungarian — unambiguous (NOT anchored to end — catches "Xyz Kft. extra text")
    (r"\bKft\.?\b",     "Magyarország", "high"),
    (r"\bBt\.?\b",      "Magyarország", "high"),
    (r"\bZrt\.?\b",     "Magyarország", "high"),
    (r"\bNyrt\.?\b",    "Magyarország", "high"),
    # Polish — fairly unambiguous
    (r"\bSp\.?\s*z\.?\s*o\.?\s*o\.?\b", "Lengyelország", "high"),
    # Croatian/Slovenian/Bosnian — d.o.o. is unambiguous for region
    (r"\bd\.?\s*o\.?\s*o\.?\b",  None, "medium"),  # handled specially below
    # Finnish — unambiguous
    (r"\bOyj\b",        "Finnország", "high"),
    # Danish — unambiguous
    (r"\bApS\b",        "Dánia", "high"),
    (r"\bA/S\b",        "Dánia", "medium"),
    # Swedish — fairly unambiguous
    (r"\bAB\b",         "Svédország", "medium"),
    # Spanish — SLU is unambiguous
    (r"\bSLU\b",        "Spanyolország", "high"),
    (r"\bS\.?L\.?\b",   "Spanyolország", "medium"),
]

# Country names that may appear embedded in partner name
EMBEDDED_COUNTRY_PATTERNS = [
    (r"\bOroszorsz[aá]g\b",          "Oroszország"),
    (r"\bN[eé]metorsz[aá]g\b",      "Németország"),
    (r"\bAusztria\b",                "Ausztria"),
    (r"\bSv[aá]jc\b",               "Svájc"),
    (r"\bMagyarorsz[aá]g\b",        "Magyarország"),
    (r"\bKína\b",                    "Kína"),
    (r"\bFranciaorsz[aá]g\b",       "Franciaország"),
    (r"\bOlaszorsz[aá]g\b",         "Olaszország"),
    (r"\bHorvátország\b",           "Horvátország"),
    (r"\bRom[aá]nia\b",             "Románia"),
    (r"\b\.hu\b",                    "Magyarország"),  # website ending in .hu
    (r"\bMo[\.\-]i\s+Fi[oó]k",      "Magyarország"),  # Mo-i Fióktelep
]

# Ambiguous suffixes — flag them but do NOT auto-resolve country
AMBIGUOUS_SUFFIXES = [
    (r"\bGmbH\b",       "DE/AT/CH"),
    (r"\bAG\b",         "DE/AT/CH"),
    (r"\bGesmbH\b",     "AT (likely)"),
    (r"\bs\.?\s*r\.?\s*o\.?\b", "CZ/SK"),
    (r"\bS\.?\s*r\.?\s*l\.?\b", "IT/RO"),
    (r"\bLtd\.?\b",     "GB/international"),
    (r"\bSA\b",         "FR/ES/RO/CH"),
    (r"\bSAS\b",        "FR"),
    (r"\bB\.?\s*V\.?\b", "NL/BE"),
    (r"\bN\.?\s*V\.?\b", "NL/BE"),
    (r"\bSE\b",         "EU (Societas Europaea)"),
]


# ══════════════════════════════════════════════════════════════════════════════
#  Core logic
# ══════════════════════════════════════════════════════════════════════════════

def create_table(conn):
    """Create country_resolutions table if not exists."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    log.info("Table country_resolutions ready")


def collect_tg1_partners():
    """Collect all unique TG1 partners across all years, with their raw names."""
    partners = {}  # norm → {raw, years, domestic_flags}

    for year in range(2020, 2027):
        key = f"TG1_{year}"
        if key not in FILE_CONFIG:
            continue
        try:
            quotes = extract_tg1_quotes(key)
        except Exception as e:
            log.warning(f"  Could not extract {key}: {e}")
            continue

        for r in quotes:
            name = r.get("partner_name")
            if not name:
                continue
            norm = normalize_name(name)
            if not norm:
                continue

            if norm not in partners:
                partners[norm] = {
                    "raw": str(name).strip(),
                    "years": set(),
                    "country_name": None,
                    "domestic_flag": None,
                }
            partners[norm]["years"].add(year)

            # Capture country data if available
            cn = r.get("country_name")
            if cn and isinstance(cn, str) and cn.strip() not in MISSING_MARKERS:
                partners[norm]["country_name"] = cn.strip()

            df = r.get("country_domestic")
            if df and isinstance(df, str) and df.strip() not in MISSING_MARKERS:
                partners[norm]["domestic_flag"] = df.strip()

    log.info(f"Collected {len(partners)} unique TG1 partners from quotes")
    return partners


def build_tg2_country_lookup():
    """Build a normalized_name → country dict from all TG2 data."""
    lookup = {}  # norm → {country, source}

    for year in range(2022, 2027):
        key = f"TG2_{year}"
        if key not in FILE_CONFIG:
            continue
        try:
            headers, _ = extract_tg2_quotes(key)
        except Exception as e:
            log.warning(f"  Could not extract {key}: {e}")
            continue

        for r in headers:
            name = r.get("partner_name")
            country = r.get("country")
            if not name or not country:
                continue
            if isinstance(country, str) and country.strip() in MISSING_MARKERS:
                continue

            norm = normalize_name(name)
            if norm:
                country_clean = str(country).strip()
                # Prefer newer year data
                lookup[norm] = {
                    "country": country_clean,
                    "source": f"TG2_{year} row {r.get('_row', '?')}",
                }

    # Also check TG2 partner lists
    for year in range(2023, 2027):
        key = f"TG2_{year}"
        try:
            partners = extract_partners(key)
        except Exception:
            continue
        for r in partners:
            name = r.get("name")
            country = r.get("country")
            if not name or not country:
                continue
            if isinstance(country, str) and country.strip() in MISSING_MARKERS:
                continue
            norm = normalize_name(name)
            if norm:
                lookup[norm] = {
                    "country": str(country).strip(),
                    "source": f"TG2_{year} partner list",
                }

    log.info(f"Built TG2 country lookup: {len(lookup)} entries")
    return lookup


def strategy_admin_db(conn, unresolved):
    """Strategy A: resolve from admin.db partner_master (direct country field)."""
    results = []
    cursor = conn.execute(
        "SELECT name_normalized, country, partner_id FROM partner_master WHERE country IS NOT NULL AND country != ''"
    )
    admin_countries = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

    for norm in list(unresolved):
        if norm in admin_countries:
            country, pm_id = admin_countries[norm]
            results.append({
                "norm": norm,
                "raw": unresolved[norm]["raw"],
                "country": country,
                "is_domestic": 1 if country == "Magyarország" else 0,
                "method": "admin_db_partner",
                "source": f"partner_master {pm_id}: {country}",
                "confidence": "high",
            })
            del unresolved[norm]

    log.info(f"  Strategy admin_db_partner: {len(results)} resolved")
    return results


def strategy_pm_id_crossref(conn, unresolved, tg2_lookup):
    """Strategy A2: use admin.db PM-ID to bridge TG1↔TG2 country data.

    If an TG1 partner (no country) and an TG2 partner (has country) were
    matched to the same PM-ID during import wizard partner matching,
    we can transfer the TG2 country to the TG1 partner.
    """
    results = []

    # Build PM-ID → TG2 country mapping via aliases
    # 1. Get all aliases with their PM-IDs
    cursor = conn.execute(
        "SELECT partner_id, name_normalized FROM partner_aliases"
    )
    alias_rows = cursor.fetchall()

    # 2. Group aliases by PM-ID
    pm_to_norms = {}  # pm_id → set of normalized names
    for pm_id, norm in alias_rows:
        pm_to_norms.setdefault(pm_id, set()).add(norm)

    # Also add partner_master normalized names
    cursor = conn.execute(
        "SELECT partner_id, name_normalized FROM partner_master"
    )
    for pm_id, norm in cursor.fetchall():
        pm_to_norms.setdefault(pm_id, set()).add(norm)

    # 3. For each PM-ID, find if any associated name has TG2 country data
    pm_country = {}  # pm_id → {country, source}
    for pm_id, norms in pm_to_norms.items():
        for norm in norms:
            if norm in tg2_lookup:
                pm_country[pm_id] = tg2_lookup[norm]
                break

    # 4. Build reverse lookup: norm → pm_id (for unresolved TG1 partners)
    norm_to_pm = {}
    for pm_id, norms in pm_to_norms.items():
        for norm in norms:
            norm_to_pm[norm] = pm_id

    # 5. Resolve unresolved TG1 partners via PM-ID bridge
    for norm in list(unresolved):
        pm_id = norm_to_pm.get(norm)
        if pm_id and pm_id in pm_country:
            entry = pm_country[pm_id]
            country = entry["country"]
            results.append({
                "norm": norm,
                "raw": unresolved[norm]["raw"],
                "country": country,
                "is_domestic": 1 if country == "Magyarország" else 0,
                "method": "pm_id_crossref",
                "source": f"PM-ID {pm_id} → TG2: {entry['source']}",
                "confidence": "high",
            })
            del unresolved[norm]

    log.info(f"  Strategy pm_id_crossref: {len(results)} resolved")
    return results


def strategy_tg1_2025(unresolved, tg1_partners):
    """Strategy B: resolve from TG1 2025 quote/partner data."""
    results = []

    for norm in list(unresolved):
        info = tg1_partners.get(norm)
        if not info:
            continue
        cn = info.get("country_name")
        if cn and cn not in MISSING_MARKERS:
            results.append({
                "norm": norm,
                "raw": unresolved[norm]["raw"],
                "country": cn,
                "is_domestic": 1 if cn == "Magyarország" else 0,
                "method": "tg1_2025_data",
                "source": f"TG1_2025 country_name: {cn}",
                "confidence": "high",
            })
            del unresolved[norm]

    log.info(f"  Strategy tg1_2025_data: {len(results)} resolved")
    return results


def strategy_tg2_crossref(unresolved, tg2_lookup):
    """Strategy C: cross-reference with TG2 country data."""
    results = []

    for norm in list(unresolved):
        if norm in tg2_lookup:
            entry = tg2_lookup[norm]
            country = entry["country"]
            # Validate country is in our map or known
            results.append({
                "norm": norm,
                "raw": unresolved[norm]["raw"],
                "country": country,
                "is_domestic": 1 if country == "Magyarország" else 0,
                "method": "tg2_crossref",
                "source": entry["source"],
                "confidence": "high",
            })
            del unresolved[norm]

    log.info(f"  Strategy tg2_crossref: {len(results)} resolved")
    return results


def strategy_tg1_domestic(unresolved, tg1_partners):
    """Strategy D: use TG1 2020-2022 domestic flag (M=Magyar, W=foreign)."""
    results = []

    for norm in list(unresolved):
        info = tg1_partners.get(norm)
        if not info:
            continue
        df = info.get("domestic_flag")
        if not df:
            continue

        df_upper = str(df).strip().upper()
        if df_upper == "M":
            results.append({
                "norm": norm,
                "raw": unresolved[norm]["raw"],
                "country": "Magyarország",
                "is_domestic": 1,
                "method": "tg1_domestic_flag",
                "source": f"TG1 domestic flag: M (years: {sorted(info['years'])})",
                "confidence": "medium",
            })
            del unresolved[norm]
        elif df_upper == "W":
            # We know it's foreign but not which country — still useful info
            results.append({
                "norm": norm,
                "raw": unresolved[norm]["raw"],
                "country": None,  # unknown specific country
                "is_domestic": 0,
                "method": "tg1_domestic_flag",
                "source": f"TG1 domestic flag: W=Külföld (years: {sorted(info['years'])})",
                "confidence": "low",
            })
            # Keep in unresolved — country still needed
            # But record the partial info
            # Don't delete from unresolved, the flag info is saved but country TBD

    log.info(f"  Strategy tg1_domestic_flag: {len(results)} resolved (partial: W=foreign stays unresolved)")
    return results


def strategy_suffix(unresolved):
    """Strategy E: detect country from company name suffix + embedded country names."""
    results = []

    for norm in list(unresolved):
        raw = unresolved[norm]["raw"]

        # Try unambiguous suffixes
        matched = False
        for pattern, country, confidence in SUFFIX_COUNTRY:
            if re.search(pattern, raw, re.IGNORECASE):
                if country is None:
                    # d.o.o. — need more context, skip auto-resolve
                    unresolved[norm]["suffix_hint"] = "HR/SI/BA (d.o.o.)"
                    continue
                results.append({
                    "norm": norm,
                    "raw": raw,
                    "country": country,
                    "is_domestic": 1 if country == "Magyarország" else 0,
                    "method": "auto_suffix",
                    "source": f"Suffix match: {pattern.strip()} → {country}",
                    "confidence": confidence,
                })
                del unresolved[norm]
                matched = True
                break

        if not matched:
            # Try embedded country name patterns
            for pattern, country in EMBEDDED_COUNTRY_PATTERNS:
                if re.search(pattern, raw, re.IGNORECASE):
                    results.append({
                        "norm": norm,
                        "raw": raw,
                        "country": country,
                        "is_domestic": 1 if country == "Magyarország" else 0,
                        "method": "auto_suffix",
                        "source": f"Embedded country: '{pattern}' → {country}",
                        "confidence": "medium",
                    })
                    del unresolved[norm]
                    matched = True
                    break

        if not matched:
            # Check ambiguous suffixes — record as hint but don't resolve
            for pattern, hint in AMBIGUOUS_SUFFIXES:
                if re.search(pattern, raw, re.IGNORECASE):
                    unresolved[norm]["suffix_hint"] = hint
                    break

    log.info(f"  Strategy auto_suffix: {len(results)} resolved")
    return results


def save_resolutions(conn, all_results, preserve_manual=True):
    """Save resolutions to admin.db. Preserves manual entries by default."""
    now = datetime.now().isoformat()

    if preserve_manual:
        # Delete only system-resolved rows (preserve manual)
        conn.execute("DELETE FROM country_resolutions WHERE resolved_by = 'system'")
    else:
        conn.execute("DELETE FROM country_resolutions")

    inserted = 0
    for r in all_results:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO country_resolutions
                (partner_name_raw, partner_name_normalized, resolved_country,
                 is_domestic, resolution_method, source_detail,
                 resolved_at, resolved_by, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'system', ?)
            """, (
                r["raw"], r["norm"], r.get("country"),
                r.get("is_domestic"), r["method"], r.get("source"),
                now, r["confidence"],
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            # Manual entry exists — skip
            pass

    conn.commit()
    log.info(f"Saved {inserted} resolutions to admin.db")


def export_unresolved(unresolved, tg1_partners):
    """Export unresolved partners to CSV for manual work."""
    csv_path = DATA_DIR / "unresolved_countries.csv"

    rows = []
    for norm, info in sorted(unresolved.items()):
        tg1_info = tg1_partners.get(norm, {})
        rows.append({
            "partner_name_raw": info["raw"],
            "partner_name_normalized": norm,
            "years_seen": ", ".join(str(y) for y in sorted(info.get("years", tg1_info.get("years", set())))),
            "suffix_hint": info.get("suffix_hint", ""),
            "known_info": info.get("known_info", ""),
            "resolved_country": "",  # User fills this in
            "website": "",           # Company website
            "tax_id": "",            # HU adószám (magyar) VAGY EU VAT (EU) — non-EU: üresen hagyni
        })

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "partner_name_raw", "partner_name_normalized",
            "years_seen", "suffix_hint", "known_info", "resolved_country",
            "website", "tax_id"
        ], delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    log.info(f"Exported {len(rows)} unresolved partners to {csv_path}")
    return csv_path


def import_manual_csv(conn, csv_path=None):
    """Import manually filled CSV back into country_resolutions + partner_master updates."""
    if csv_path is None:
        csv_path = DATA_DIR / "unresolved_countries.csv"
    else:
        csv_path = Path(csv_path)

    if not csv_path.exists():
        log.warning(f"No CSV found at {csv_path}")
        return 0

    now = datetime.now().isoformat()
    imported = 0
    websites_updated = 0

    # Try UTF-8 first, fall back to latin-1 (Windows)
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(csv_path, "r", encoding=enc) as f:
                f.read(1024)  # test read
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    with open(csv_path, "r", encoding=enc) as f:
        # Auto-detect delimiter (semicolon or tab)
        sample = f.read(1024)
        delim = "\t" if "\t" in sample else ";"
        f.seek(0)
        reader = csv.DictReader(f, delimiter=delim)
        for row in reader:
            norm = (row.get("partner_name_normalized") or "").strip()
            raw = (row.get("partner_name_raw") or "").strip()
            country = (row.get("resolved_country") or "").strip()
            website = (row.get("website") or row.get("company website") or "").strip()
            tax_id = (row.get("tax_id") or "").strip()

            # Save country resolution
            if country:
                is_dom = 1 if country == "Magyarország" else 0
                conn.execute("""
                    INSERT OR REPLACE INTO country_resolutions
                    (partner_name_raw, partner_name_normalized, resolved_country,
                     is_domestic, resolution_method, source_detail,
                     resolved_at, resolved_by, confidence)
                    VALUES (?, ?, ?, ?, 'manual', ?, ?, 'user', 'high')
                """, (raw, norm, country, is_dom,
                      f"Manual CSV import at {now}", now))
                imported += 1

            # Find partner_id for this partner (direct or via alias)
            pm_id = None
            pm_row = conn.execute(
                "SELECT partner_id FROM partner_master WHERE name_normalized = ?", (norm,)
            ).fetchone()
            if pm_row:
                pm_id = pm_row[0]
            else:
                alias_row = conn.execute(
                    "SELECT partner_id FROM partner_aliases WHERE name_normalized = ? LIMIT 1",
                    (norm,)
                ).fetchone()
                if alias_row:
                    pm_id = alias_row[0]

            if pm_id:
                # Save website
                if website:
                    upd = conn.execute(
                        "UPDATE partner_master SET website = ?, updated_at = ? "
                        "WHERE partner_id = ? AND (website IS NULL OR website = '')",
                        (website, now, pm_id)
                    ).rowcount
                    if upd:
                        websites_updated += 1

                # Save tax ID: HU adószám → tax_id_hu, EU VAT → vat_eu
                if tax_id:
                    if tax_id.upper().startswith("HU") or (country == "Magyarország" and not tax_id.upper()[:2].isalpha()):
                        # Hungarian tax ID
                        conn.execute(
                            "UPDATE partner_master SET tax_id_hu = ?, updated_at = ? "
                            "WHERE partner_id = ? AND (tax_id_hu IS NULL OR tax_id_hu = '')",
                            (tax_id, now, pm_id)
                        )
                    elif len(tax_id) >= 2 and tax_id[:2].isalpha():
                        # EU VAT (starts with 2-letter country code)
                        conn.execute(
                            "UPDATE partner_master SET vat_eu = ?, updated_at = ? "
                            "WHERE partner_id = ? AND (vat_eu IS NULL OR vat_eu = '')",
                            (tax_id, now, pm_id)
                        )

    conn.commit()
    log.info(f"Imported {imported} country resolutions, {websites_updated} websites from CSV")
    return imported


def show_status(conn):
    """Show current resolution status."""
    print("\n" + "=" * 70)
    print("COUNTRY RESOLUTION STATUS")
    print("=" * 70)

    cursor = conn.execute("""
        SELECT resolution_method, confidence, COUNT(*),
               SUM(CASE WHEN resolved_country IS NOT NULL THEN 1 ELSE 0 END)
        FROM country_resolutions
        GROUP BY resolution_method, confidence
        ORDER BY resolution_method, confidence
    """)

    total = 0
    resolved = 0
    for method, conf, cnt, res in cursor.fetchall():
        print(f"  {method:25s}  {conf:8s}  {cnt:4d} entries ({res} with country)")
        total += cnt
        resolved += res

    print(f"  {'─' * 55}")
    print(f"  {'TOTAL':25s}           {total:4d} entries ({resolved} resolved)")

    # Unresolved count
    cursor = conn.execute(
        "SELECT COUNT(*) FROM country_resolutions WHERE resolved_country IS NULL"
    )
    unresolved = cursor.fetchone()[0]
    print(f"  Still unresolved: {unresolved}")

    # Country distribution
    print(f"\n  Top countries:")
    cursor = conn.execute("""
        SELECT resolved_country, COUNT(*) as cnt
        FROM country_resolutions
        WHERE resolved_country IS NOT NULL
        GROUP BY resolved_country
        ORDER BY cnt DESC
        LIMIT 15
    """)
    for country, cnt in cursor.fetchall():
        print(f"    {country:30s}  {cnt:4d}")


# ══════════════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Resolve missing country data for TG1 partners")
    parser.add_argument("--status", action="store_true", help="Show current resolution status")
    parser.add_argument("--import-csv", action="store_true", help="Import manually filled CSV")
    parser.add_argument("--csv-path", type=str, help="Path to CSV file (default: data/unresolved_countries.csv)")
    args = parser.parse_args()

    conn = sqlite3.connect(str(ADMIN_DB))
    create_table(conn)

    if args.status:
        show_status(conn)
        conn.close()
        return

    if args.import_csv:
        imported = import_manual_csv(conn, csv_path=args.csv_path)
        print(f"\nImported {imported} manual entries.")
        show_status(conn)
        conn.close()
        return

    # ── Full auto-resolution run ──────────────────────────────────────────
    print("=" * 70)
    print(f"COUNTRY RESOLUTION — {datetime.now().isoformat()}")
    print("=" * 70)

    print("\n[1/6] Collecting TG1 partners from all years...")
    tg1_partners = collect_tg1_partners()

    print("\n[2/6] Building TG2 country lookup...")
    tg2_lookup = build_tg2_country_lookup()

    # Build unresolved set: all TG1 partners
    unresolved = {}
    for norm, info in tg1_partners.items():
        unresolved[norm] = {"raw": info["raw"], "years": info["years"]}

    print(f"\n[3/6] Running resolution strategies on {len(unresolved)} partners...\n")
    all_results = []

    # Strategy A: admin.db (direct country field)
    all_results.extend(strategy_admin_db(conn, unresolved))

    # Strategy A2: PM-ID cross-reference (TG1↔TG2 via shared PM-ID in admin.db)
    all_results.extend(strategy_pm_id_crossref(conn, unresolved, tg2_lookup))

    # Strategy B: TG1 2025 data
    all_results.extend(strategy_tg1_2025(unresolved, tg1_partners))

    # Strategy C: TG2 cross-reference (name-based, for partners not yet in admin.db)
    all_results.extend(strategy_tg2_crossref(unresolved, tg2_lookup))

    # Strategy D: TG1 domestic flag
    domestic_results = strategy_tg1_domestic(unresolved, tg1_partners)
    # Separate: HU-resolved (delete from unresolved) vs W-flagged (keep)
    for r in domestic_results:
        if r["country"] == "Magyarország":
            all_results.append(r)
        else:
            # W=foreign: save the partial info but keep in unresolved
            all_results.append(r)
            # Add known_info hint to unresolved
            if r["norm"] in unresolved:
                unresolved[r["norm"]]["known_info"] = "Külföldi (TG1 domestic flag: W)"

    # Strategy E: suffix detection
    all_results.extend(strategy_suffix(unresolved))

    # ── Save results ──────────────────────────────────────────────────────
    print(f"\n[4/6] Saving {len(all_results)} resolutions to admin.db...")
    save_resolutions(conn, all_results)

    # ── Export unresolved ─────────────────────────────────────────────────
    print(f"\n[5/6] Exporting {len(unresolved)} unresolved partners...")
    csv_path = export_unresolved(unresolved, tg1_partners)

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n[6/6] Summary:")
    show_status(conn)

    print(f"\n  Unresolved list: {csv_path}")
    print(f"  Fill in 'resolved_country' column, then run:")
    print(f"    python scripts/resolve_countries.py --import-csv")

    conn.close()


if __name__ == "__main__":
    main()
