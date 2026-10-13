"""
ETL Bridge — connects the admin import wizard with the existing ETL pipeline.

Each function corresponds to one step in the import wizard flow:
  run_extract          → Step 1: read Excel files
  run_staging_transform → Step 2: partner & status staging (fuzzy match vs admin.db)
  resolve_partners     → Step 3: build partner lookup from reviewed staging rows
  run_full_transform   → Step 4: full ETL transform using resolved partner lookup
  collect_blocking_issues → Step 5: data quality gate
  commit               → Step 6: write dashboard.db, export JSON, generate HTML

IMPORTANT: ETL modules use `from config import ...` style (relative to etl/).
           We add the etl/ directory to sys.path before importing.
"""
import logging
import sqlite3
import sys
from difflib import SequenceMatcher
from pathlib import Path

log = logging.getLogger(__name__)

# ── sys.path setup ────────────────────────────────────────────────────────────
_ETL_DIR = Path(__file__).resolve().parent.parent / "etl"
if str(_ETL_DIR) not in sys.path:
    sys.path.insert(0, str(_ETL_DIR))

# ── Project root (needed for dashboard.html output path) ──────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Admin DB path (direct sqlite3, not Flask g) ───────────────────────────────
# Computed independently so this module works outside a Flask request context.
_ADMIN_DB_PATH = _PROJECT_ROOT / "admin" / "admin.db"


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _admin_conn():
    """Return a sqlite3 connection to admin.db (caller must close it)."""
    if not _ADMIN_DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(_ADMIN_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _import_etl():
    """Lazy-import ETL modules (they depend on sys.path having etl/)."""
    import config as etl_config
    import extract as etl_extract
    import transform as etl_transform
    import load as etl_load
    import export_json as etl_export
    import generate_dashboard as etl_gen
    return etl_config, etl_extract, etl_transform, etl_load, etl_export, etl_gen


# ══════════════════════════════════════════════════════════════════════════════
#  1. run_extract
# ══════════════════════════════════════════════════════════════════════════════

def run_extract(file_paths: dict) -> tuple:
    """
    Extract raw data from the provided Excel files.

    Parameters
    ----------
    file_paths : dict
        Mapping of file key → Path, e.g.
        {"TG1_2025": Path(...), "TG1_2026": Path(...), ...}
        Only keys present in file_paths are extracted.

    Returns
    -------
    (raw_data, summary)
        raw_data : dict  — keys like 'tg1_quotes_2025', 'tg2_headers_2025', etc.
        summary  : dict  — {file_key: {"rows": N}, ...}
    """
    etl_config, etl_extract, _, _, _, _ = _import_etl()

    # Temporarily patch config with the provided paths
    original_excel_files = dict(etl_config.EXCEL_FILES)
    original_sheets = dict(etl_config.SHEETS)
    original_start_row = dict(etl_config.DATA_START_ROW)
    etl_config.EXCEL_FILES.update({k: Path(v) for k, v in file_paths.items()})

    # Auto-register SHEETS and DATA_START_ROW for new years
    for key in file_paths:
        pline, year = key.split("_")  # TG1_2025 → TG1, 2025
        if key not in etl_config.SHEETS:
            if pline == "TG1":
                etl_config.SHEETS[key] = {"quotes": year}
            else:
                etl_config.SHEETS[key] = {"quotes": year, "partners": "partnerek"}
        if key not in etl_config.DATA_START_ROW:
            etl_config.DATA_START_ROW[key] = 3  # default start row

    raw_data = {}
    summary = {}

    try:
        for key in file_paths:
            pline, year = key.split("_")

            if pline == "TG1":
                rows = etl_extract.extract_tg1_quotes(key)
                raw_data[f"tg1_quotes_{year}"] = rows
                summary[key] = {"rows": len(rows)}

                # Partner list (only TG1 2025 has one)
                if "partners" in etl_config.SHEETS.get(key, {}):
                    try:
                        prows = etl_extract.extract_tg1_partners()
                        raw_data.setdefault("tg1_partners", []).extend(prows)
                    except Exception:
                        pass

                # Contacts (only TG1 2025 has one)
                if "contacts" in etl_config.SHEETS.get(key, {}):
                    try:
                        crows = etl_extract.extract_tg1_contacts()
                        raw_data.setdefault("tg1_contacts", []).extend(crows)
                    except Exception:
                        pass

            elif pline == "TG2":
                headers, lines = etl_extract.extract_tg2_quotes(key)
                raw_data[f"tg2_headers_{year}"] = headers
                raw_data[f"tg2_lines_{year}"] = lines
                summary[key] = {"rows": len(headers) + len(lines)}

                # Partner list
                if "partners" in etl_config.SHEETS.get(key, {}):
                    try:
                        prows = etl_extract.extract_tg2_partners(key)
                        raw_data[f"tg2_partners_{year}"] = prows
                    except Exception:
                        pass

    finally:
        # Always restore original config
        etl_config.EXCEL_FILES.clear()
        etl_config.EXCEL_FILES.update(original_excel_files)
        etl_config.SHEETS.clear()
        etl_config.SHEETS.update(original_sheets)
        etl_config.DATA_START_ROW.clear()
        etl_config.DATA_START_ROW.update(original_start_row)

    log.info("run_extract complete: %s", {k: v["rows"] for k, v in summary.items()})
    return raw_data, summary


# ══════════════════════════════════════════════════════════════════════════════
#  2. run_staging_transform
# ══════════════════════════════════════════════════════════════════════════════

def run_staging_transform(raw_data: dict) -> tuple:
    """
    Build partner staging and status staging for operator review.

    Partner staging
    ---------------
    For each unique raw partner name found in raw_data:
      - Normalize with transform.normalize_name()
      - Fuzzy-match against partner_master (name_normalized) AND partner_aliases
        (name_normalized) in admin.db using SequenceMatcher
      - Assign zone: green (≥0.95), yellow (≥0.85), red (<0.85)
      - Count occurrences across all quote/header lists
      - Determine which source file(s) the name appears in

    Status staging
    --------------
    For each unique raw status value found in raw_data:
      - Check against status_dictionary in admin.db
      - Check against config.STATUS_MAP
      - Report known/unknown + suggested normalization

    Returns
    -------
    (partner_staging, status_staging)
        partner_staging : list of dicts — one per unique raw partner name
        status_staging  : list of dicts — one per unique raw status value
    """
    _, _, etl_transform, _, _, _ = _import_etl()
    import config as etl_config

    # ── Collect partner name occurrences ──────────────────────────────────────
    # occurrence_map: raw_name → {count, sources (set of file keys)}
    occurrence_map: dict = {}

    def _record(name, source_file):
        if not name:
            return
        raw = str(name).strip()
        if not raw:
            return
        if raw not in occurrence_map:
            occurrence_map[raw] = {"count": 0, "sources": set()}
        occurrence_map[raw]["count"] += 1
        occurrence_map[raw]["sources"].add(source_file)

    for key, val in raw_data.items():
        if key.startswith("tg1_quotes_"):
            year = key.replace("tg1_quotes_", "")
            for r in val:
                _record(r.get("partner_name"), f"TG1_{year}")
        elif key.startswith("tg2_headers_"):
            year = key.replace("tg2_headers_", "")
            for r in val:
                _record(r.get("partner_name"), f"TG2_{year}")
        elif key.startswith("tg1_partners"):
            for r in val:
                _record(r.get("name"), "TG1")
        elif key.startswith("tg2_partners_"):
            year = key.replace("tg2_partners_", "")
            for r in val:
                _record(r.get("name"), f"TG2_{year}")

    # ── Load admin.db partner master + aliases ─────────────────────────────────
    # pm_rows: list of (name_normalized, partner_id, display_name, country, ...)
    pm_rows = []
    alias_rows = []  # (name_normalized, partner_id)

    conn = _admin_conn()
    if conn:
        try:
            cur = conn.execute(
                "SELECT partner_id, display_name, name_normalized, country, "
                "is_domestic, partner_type, industry, teaor_code FROM partner_master"
            )
            pm_rows = [dict(r) for r in cur.fetchall()]

            cur = conn.execute(
                "SELECT partner_id, name_normalized FROM partner_aliases"
            )
            alias_rows = [(r["name_normalized"], r["partner_id"]) for r in cur.fetchall()]
        finally:
            conn.close()

    # Build lookup: normalized_name → partner_master row
    pm_lookup: dict = {r["name_normalized"]: r for r in pm_rows}
    # Alias lookup: alias_normalized → partner_id
    alias_lookup: dict = {norm: pid for norm, pid in alias_rows}

    # All normalized keys in admin.db (master + aliases combined)
    all_admin_norms = list(pm_lookup.keys()) + list(alias_lookup.keys())

    def _fuzzy_match(query_norm: str):
        """Find best match in admin.db (partner_master + aliases).
        Returns (score, pm_id, pm_row) or (0.0, None, None).
        """
        if not query_norm or len(query_norm) < 2:
            return 0.0, None, None

        best_score = 0.0
        best_pm_id = None

        for admin_norm in all_admin_norms:
            # Quick length pre-filter
            max_len = max(len(query_norm), len(admin_norm))
            if max_len > 0 and abs(len(query_norm) - len(admin_norm)) / max_len > 0.4:
                continue
            score = SequenceMatcher(None, query_norm, admin_norm).ratio()
            if score > best_score:
                best_score = score
                # Resolve the PM id: prefer direct match, else alias
                if admin_norm in pm_lookup:
                    best_pm_id = pm_lookup[admin_norm]["partner_id"]
                else:
                    best_pm_id = alias_lookup.get(admin_norm)

        pm_row = pm_lookup.get(
            next((n for n in pm_lookup if
                  pm_lookup[n]["partner_id"] == best_pm_id), None),
            None
        )
        return best_score, best_pm_id, pm_row

    # ── Build partner staging rows ─────────────────────────────────────────────
    partner_staging = []
    for raw_name, info in occurrence_map.items():
        name_normalized = etl_transform.normalize_name(raw_name)
        score, pm_id, pm_row = _fuzzy_match(name_normalized)

        if score >= 0.95:
            zone = "green"
        elif score >= 0.85:
            zone = "yellow"
        else:
            zone = "red"

        partner_staging.append({
            "raw_name": raw_name,
            "name_normalized": name_normalized,
            "match_score": round(score, 4),
            "matched_pm_id": pm_id,
            "matched_name": pm_row["display_name"] if pm_row else None,
            "zone": zone,
            "occurrence_count": info["count"],
            "source_file": ", ".join(sorted(info["sources"])),
            # Extra enrichment fields from matched partner master row
            "country": pm_row["country"] if pm_row else None,
        })

    partner_staging.sort(key=lambda r: (-r["occurrence_count"], r["zone"], r["raw_name"]))

    # ── Collect status occurrences ─────────────────────────────────────────────
    status_count: dict = {}

    def _count_status(s):
        if s is None:
            return
        raw = str(s).strip()
        if raw:
            status_count[raw] = status_count.get(raw, 0) + 1

    for key, val in raw_data.items():
        if key.startswith("tg1_quotes_") or key.startswith("tg2_headers_"):
            for r in val:
                _count_status(r.get("status"))

    # Load status_dictionary from admin.db
    db_statuses: dict = {}
    conn = _admin_conn()
    if conn:
        try:
            cur = conn.execute(
                "SELECT raw_status, normalized FROM status_dictionary"
            )
            for row in cur.fetchall():
                db_statuses[row["raw_status"]] = row["normalized"]
        finally:
            conn.close()

    status_staging = []
    for raw_status, count in sorted(status_count.items(), key=lambda x: -x[1]):
        # Check admin.db status_dictionary first, then ETL config.STATUS_MAP
        key_lower = raw_status.strip().lower()
        if raw_status in db_statuses:
            known = True
            normalized = db_statuses[raw_status]
        elif key_lower in etl_config.STATUS_MAP:
            known = True
            normalized = etl_config.STATUS_MAP[key_lower][0]
        else:
            # Try strip-accent variant
            import unicodedata
            def _strip_acc(s):
                return "".join(c for c in unicodedata.normalize("NFKD", s)
                               if not unicodedata.combining(c))
            key_ascii = _strip_acc(key_lower)
            match = next(
                (v[0] for k, v in etl_config.STATUS_MAP.items()
                 if _strip_acc(k) == key_ascii),
                None
            )
            if match:
                known = True
                normalized = match
            else:
                known = False
                normalized = None

        status_staging.append({
            "raw_status": raw_status,
            "quote_count": count,
            "known": known,
            "normalized": normalized,
        })

    log.info(
        "run_staging_transform: %d unique partners, %d unique statuses",
        len(partner_staging), len(status_staging),
    )
    return partner_staging, status_staging


# ══════════════════════════════════════════════════════════════════════════════
#  3. resolve_partners
# ══════════════════════════════════════════════════════════════════════════════

def resolve_partners(session_id: str) -> dict:
    """
    Build a partner lookup dict from the reviewed staging rows for this session.

    Reads staging_partners rows from admin.db (decision must be set).
    For 'accept' / 'reassign' decisions: look up the matched_pm_id in partner_master.
    For 'new' decisions: the new_pm_id should already be set in staging_partners.

    Returns
    -------
    dict
        name_normalized → partner_dict (matches the structure that
        transform.build_partner_registry() returns, with at minimum:
        partner_id, name, name_normalized, country, is_domestic,
        partner_type, industry, teaor_code, source)
    """
    conn = _admin_conn()
    if conn is None:
        log.warning("resolve_partners: admin.db not found, returning empty lookup")
        return {}

    try:
        # Load all staging rows for this session
        cur = conn.execute(
            """SELECT raw_name, name_normalized, decision, matched_pm_id, new_pm_id
               FROM staging_partners
               WHERE session_id = ?""",
            (session_id,),
        )
        staging_rows = [dict(r) for r in cur.fetchall()]

        # Collect all PM IDs we need to look up
        pm_ids_needed = set()
        for row in staging_rows:
            if row["decision"] in ("accept", "reassign") and row["matched_pm_id"]:
                pm_ids_needed.add(row["matched_pm_id"])
            elif row["decision"] == "new" and row["new_pm_id"]:
                pm_ids_needed.add(row["new_pm_id"])

        # Bulk-load partner_master rows
        pm_data: dict = {}
        if pm_ids_needed:
            placeholders = ",".join("?" * len(pm_ids_needed))
            cur = conn.execute(
                f"""SELECT partner_id, display_name, name_normalized, country,
                           is_domestic, partner_type, industry, teaor_code
                    FROM partner_master
                    WHERE partner_id IN ({placeholders})""",
                list(pm_ids_needed),
            )
            for r in cur.fetchall():
                pm_data[r["partner_id"]] = dict(r)

    finally:
        conn.close()

    # Build lookup: name_normalized → partner_dict
    partner_lookup: dict = {}
    for row in staging_rows:
        norm = row["name_normalized"]
        decision = row["decision"]

        if decision in ("accept", "reassign"):
            pm_id = row["matched_pm_id"]
        elif decision == "new":
            pm_id = row["new_pm_id"]
        else:
            # Unresolved staging row — skip (shouldn't happen in practice)
            log.warning(
                "resolve_partners: unresolved staging row for %r (decision=%r)",
                row["raw_name"], decision,
            )
            continue

        pm_row = pm_data.get(pm_id)
        if pm_row is None:
            log.warning(
                "resolve_partners: PM id %r not found in partner_master (name=%r)",
                pm_id, row["raw_name"],
            )
            continue

        partner_dict = {
            "partner_id": pm_row["partner_id"],
            "name": pm_row["display_name"],
            "name_normalized": pm_row["name_normalized"],
            "official_name": None,
            "tax_id": None,
            "country": pm_row["country"],
            "is_domestic": pm_row["is_domestic"],
            "partner_type": pm_row["partner_type"],
            "industry": pm_row["industry"],
            "teaor_code": pm_row["teaor_code"],
            "first_contact_date": None,
            "source": "admin",
        }
        partner_lookup[norm] = partner_dict

    log.info("resolve_partners: built lookup with %d entries", len(partner_lookup))
    return partner_lookup


# ══════════════════════════════════════════════════════════════════════════════
#  4. run_full_transform
# ══════════════════════════════════════════════════════════════════════════════

def run_full_transform(raw_data: dict, partner_lookup: dict) -> dict:
    """
    Run the full ETL transform using the operator-resolved partner lookup.

    Parameters
    ----------
    raw_data       : dict — output of run_extract()
    partner_lookup : dict — output of resolve_partners()
                           name_normalized → partner_dict

    Returns
    -------
    dict — the transformed data dict (partners, quotes, quote_lines, etc.)
    """
    _, _, etl_transform, _, _, _ = _import_etl()

    transformed = etl_transform.transform_all(
        raw_data, external_lookup=partner_lookup if partner_lookup else None
    )
    log.info(
        "run_full_transform: %d partners, %d quotes, %d quote lines",
        len(transformed.get("partners", [])),
        len(transformed.get("quotes", [])),
        len(transformed.get("quote_lines", [])),
    )
    return transformed


# ══════════════════════════════════════════════════════════════════════════════
#  5. collect_blocking_issues
# ══════════════════════════════════════════════════════════════════════════════

def collect_blocking_issues(transformed: dict) -> list:
    """
    Scan transformed data for blocking issues and warnings.

    BLOCKING
    --------
    - WON status + work_number is NULL          → type='won_no_work'
    - partner_id is NULL                        → type='partner_null'

    WARNING
    -------
    - reaction_days > 90                        → type='slow_reaction'
    - country is NULL (on partner)              → type='missing_country'
    - request_date is NULL (status not in
      NO_QUOTE / NOT_RELEVANT)                  → type='missing_date'

    Returns
    -------
    list of dicts — [{severity, issue_type, quote_id, detail}, ...]
    """
    issues = []

    non_data_statuses = {"NO_QUOTE", "NOT_RELEVANT", "ORDER_LINE", "LOST_CUSTOMER"}

    for q in transformed.get("quotes", []):
        qid = q.get("quote_id", "?")
        status = q.get("status")

        # BLOCKING: WON without work number
        if status == "WON" and not q.get("work_number"):
            issues.append({
                "severity": "blocking",
                "issue_type": "won_no_work",
                "quote_id": qid,
                "detail": f"{qid}: státusz WON de nincs munkaszám",
            })

        # Partner missing
        if q.get("partner_id") is None:
            raw_name = q.get("partner_name_raw")
            if raw_name and str(raw_name).strip() and str(raw_name).strip().lower() != "none":
                # Has a raw name but no match — blocking (operator should have resolved it)
                severity = "blocking"
            else:
                # No partner name in Excel at all (e.g. TG1 2026 #REF! columns) — warning only
                severity = "warning"
            issues.append({
                "severity": severity,
                "issue_type": "partner_null",
                "quote_id": qid,
                "detail": (
                    f"{qid}: partner_id NULL "
                    f"(nyers név: {raw_name or '—'})"
                ),
            })

        # WARNING: slow reaction
        rd = q.get("reaction_days")
        if rd is not None and rd > 90:
            issues.append({
                "severity": "warning",
                "issue_type": "slow_reaction",
                "quote_id": qid,
                "detail": f"{qid}: reakcióidő {int(rd)} nap (>90)",
            })

        # WARNING: missing request date (skip non-actionable statuses)
        if q.get("request_date") is None and status not in non_data_statuses:
            issues.append({
                "severity": "warning",
                "issue_type": "missing_date",
                "quote_id": qid,
                "detail": f"{qid}: nincs ajánlatkérés dátum",
            })

    # WARNING: partner without country
    for p in transformed.get("partners", []):
        if p.get("country") is None:
            issues.append({
                "severity": "warning",
                "issue_type": "missing_country",
                "quote_id": None,
                "detail": (
                    f"Partner {p.get('partner_id', '?')} "
                    f"({p.get('name', '?')}): nincs ország"
                ),
            })

    blocking = sum(1 for i in issues if i["severity"] == "blocking")
    warnings = sum(1 for i in issues if i["severity"] == "warning")
    log.info(
        "collect_blocking_issues: %d blocking, %d warnings", blocking, warnings
    )
    return issues


# ══════════════════════════════════════════════════════════════════════════════
#  6. commit
# ══════════════════════════════════════════════════════════════════════════════

def commit(transformed: dict) -> Path:
    """
    Write the final output: dashboard.db → dashboard_data.json → dashboard.html.

    Parameters
    ----------
    transformed : dict — output of run_full_transform()

    Returns
    -------
    Path — absolute path to the written dashboard.html
    """
    _, _, _, etl_load, etl_export, etl_gen = _import_etl()

    # 1. Write dashboard.db
    etl_load.load_all(transformed)
    log.info("commit: dashboard.db written")

    # 2. Export JSON
    etl_export.export()
    log.info("commit: dashboard_data.json exported")

    # 3. Generate HTML
    html = etl_gen.generate()
    log.info("commit: dashboard HTML generated")

    # 4. Write HTML to project root
    html_path = _PROJECT_ROOT / "dashboard.html"
    html_path.write_text(html, encoding="utf-8")
    log.info("commit: dashboard.html written to %s", html_path)

    return html_path
