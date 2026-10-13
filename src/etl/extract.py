"""
Extract — read raw data from Excel files using openpyxl.
Returns lists of dicts (one per row) for each data source.

Uses row-iterator mode for read_only workbooks (much faster than cell-by-cell).
"""
import logging
from openpyxl import load_workbook
from config import FILE_CONFIG, MISSING_MARKERS

log = logging.getLogger(__name__)

# Maximum number of consecutive empty rows before we stop reading
MAX_EMPTY_STREAK = 20


def _clean(v):
    """Clean a cell value; return None for missing markers."""
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        if v in MISSING_MARKERS or v == "":
            return None
    return v


def _read_sheet(filepath, sheetname, col_map, start_row, *,
                row_filter=None, stop_on_empty=False):
    """
    Generic sheet reader using openpyxl row iterator.
    col_map: dict of field_name → 1-based column index.
    stop_on_empty: if True, stop after MAX_EMPTY_STREAK consecutive rows
                   where the first col_map field is None (for sheets that
                   extend to Excel max row).
    """
    wb = load_workbook(filepath, read_only=True, data_only=True)
    ws = wb[sheetname]

    # Determine max column needed
    max_col = max(col_map.values())

    rows = []
    empty_streak = 0
    # Field name of the first column in the map (used for empty detection)
    first_field = next(iter(col_map))

    for row_idx, row_cells in enumerate(ws.iter_rows(min_row=start_row,
                                                      max_col=max_col,
                                                      values_only=False), start=start_row):
        # Build cell value list (0-indexed)
        cell_vals = [c.value for c in row_cells]

        record = {}
        for field, col in col_map.items():
            idx = col - 1  # 0-based
            val = cell_vals[idx] if idx < len(cell_vals) else None
            record[field] = _clean(val)

        # Stop-on-empty: bail out when we hit too many consecutive empty rows
        if stop_on_empty:
            if record.get(first_field) is None:
                empty_streak += 1
                if empty_streak >= MAX_EMPTY_STREAK:
                    break
                continue
            else:
                empty_streak = 0

        if row_filter and not row_filter(record):
            continue

        record["_row"] = row_idx
        rows.append(record)

    wb.close()
    return rows


def _get_cfg(file_key):
    """Get FILE_CONFIG entry, raise clear error if missing."""
    cfg = FILE_CONFIG.get(file_key)
    if not cfg:
        raise KeyError(f"No FILE_CONFIG entry for '{file_key}'. "
                       f"Known keys: {sorted(FILE_CONFIG.keys())}")
    return cfg


# ── Status derivation helpers (pre-2023 files) ───────────────────────────────

def _derive_tg1_status_bitmask(rec):
    """Derive status string from TG1 2022-style bitmask columns (cols 25-29)."""
    if rec.get("_status_won"):
        return "megnyertük"
    if rec.get("_status_lost"):
        return "nem mi nyertük (elveszített)"
    if rec.get("_status_postponed"):
        return "vevő, elhalasztotta"
    if rec.get("_status_rejected"):
        return "nem készült árajánlat"
    if rec.get("_status_open"):
        return "kiajánlott (élő)"
    # No bitmask value — infer from other data
    if rec.get("sent_date"):
        return "kiajánlott (élő)"
    return "árajánlatra vár"


def _derive_tg2_status_feedback(rec):
    """Derive status string from TG2 2022-style feedback column."""
    feedback = (rec.get("_feedback") or "").strip().lower()
    if not feedback:
        if rec.get("sent_date"):
            return "kiajánlott"
        return "árajánlatra vár"
    # "lerendelték" / "megrendelték" = WON (but NOT "mástól rendelték", "nem rendelt")
    if "lerendel" in feedback or "megrendel" in feedback:
        return "megnyertük"
    if "visszamond" in feedback:
        return "nem készült árajánlat"
    # Non-empty feedback with sent_date = typically a loss reason
    if rec.get("sent_date"):
        return "nem mi nyertük (elveszített)"
    return "árajánlatra vár"


def _strip_internal_fields(rec):
    """Remove _-prefixed internal fields from a record."""
    for k in list(rec.keys()):
        if k.startswith("_status_") or k == "_feedback":
            del rec[k]


# ── TG1 quotes ─────────────────────────────────────────────────────────────────

def extract_tg1_quotes(file_key):
    """Extract TG1 quote rows. Supports single sheet or list of sheets (e.g. H1+H2)."""
    cfg = _get_cfg(file_key)
    has_status_col = "status" in cfg["cols"]

    sheets = cfg["sheet"]
    if isinstance(sheets, str):
        sheets = [sheets]

    def _filter(rec):
        return rec.get("quote_id") is not None and rec.get("partner_name") is not None

    rows = []
    for sheet in sheets:
        rows.extend(_read_sheet(cfg["file"], sheet, cfg["cols"], cfg["start_row"],
                                row_filter=_filter, stop_on_empty=True))

    year = int(file_key.split("_")[1])
    for r in rows:
        r["product_line"] = "TG1"
        r["year"] = year
        # Derive status from bitmask if no explicit status column (2022 and earlier)
        if not has_status_col and "_status_won" in r:
            r["status"] = _derive_tg1_status_bitmask(r)
            _strip_internal_fields(r)
    log.info("Extracted %d TG1 quotes from %s", len(rows), file_key)
    return rows


# ── TG2 quotes + line items ────────────────────────────────────────────────────

def extract_tg2_quotes(file_key):
    """
    Extract TG2 data. Returns (headers, line_items) where:
      - headers: quote header rows (one per quote)
      - line_items: detail rows ([rendelés tételsora] or continuation rows)

    Supports two modes:
      - 2023+: line items identified by status = '[rendelés tételsora]'
      - 2022:  line items are continuation rows (no quote_id) after a header
    """
    cfg = _get_cfg(file_key)
    has_status_col = "status" in cfg["cols"]

    # 2022 mode (no status col) needs all rows including continuation rows
    # with empty first field, so stop_on_empty must be False
    all_rows = _read_sheet(cfg["file"], cfg["sheet"], cfg["cols"], cfg["start_row"],
                           stop_on_empty=has_status_col)
    year = int(file_key.split("_")[1])

    headers = []
    line_items = []

    if has_status_col:
        # ── 2023+ mode: line items marked by status ──
        for r in all_rows:
            qid = r.get("quote_id")
            if qid is None or (isinstance(qid, str) and qid.strip() in ("-", "")):
                continue

            # Skip placeholder rows: quote_id exists but no partner and no status
            if not r.get("partner_name") and not (r.get("status") or "").strip():
                continue

            r["product_line"] = "TG2"
            r["year"] = year

            status_raw = (r.get("status") or "").strip().lower()
            if status_raw in ("[rendelés tételsora]", "[rendeles tetelsora]"):
                line_items.append(r)
            else:
                headers.append(r)
    else:
        # ── 2022 mode: continuation rows (no qid) are line items ──
        last_qid = None
        for r in all_rows:
            qid = r.get("quote_id")
            has_qid = qid is not None and not (isinstance(qid, str) and qid.strip() in ("-", ""))

            r["product_line"] = "TG2"
            r["year"] = year

            if has_qid:
                # Header row — derive status from feedback
                r["status"] = _derive_tg2_status_feedback(r)
                _strip_internal_fields(r)
                headers.append(r)
                last_qid = qid
            elif last_qid is not None:
                # Continuation row = line item (must have some data)
                has_data = (r.get("line_value_eur") is not None
                            or r.get("product_type") is not None
                            or r.get("quantity") is not None)
                if has_data:
                    r["quote_id"] = last_qid
                    r["status"] = "[rendelés tételsora]"
                    _strip_internal_fields(r)
                    line_items.append(r)

    log.info("Extracted %d TG2 quote headers + %d line items from %s",
             len(headers), len(line_items), file_key)
    return headers, line_items


# ── Partner lists ─────────────────────────────────────────────────────────────

def extract_partners(file_key):
    """Extract partner list from any file that has one."""
    cfg = _get_cfg(file_key)
    if "partner_sheet" not in cfg or "partner_cols" not in cfg:
        log.info("No partner sheet configured for %s", file_key)
        return []

    def _filter(rec):
        return rec.get("name") is not None

    rows = _read_sheet(cfg["file"], cfg["partner_sheet"], cfg["partner_cols"],
                       cfg.get("partner_start", 4),
                       row_filter=_filter, stop_on_empty=True)
    log.info("Extracted %d partners from %s", len(rows), file_key)
    return rows


# Legacy aliases for backward compatibility
def extract_tg1_partners():
    return extract_partners("TG1_2025")

def extract_tg2_partners(file_key):
    return extract_partners(file_key)


# ── Contact list ──────────────────────────────────────────────────────────────

def extract_tg1_contacts(file_key="TG1_2025"):
    """Extract TG1 kontaktok."""
    cfg = _get_cfg(file_key)
    if "contact_sheet" not in cfg or "contact_cols" not in cfg:
        log.info("No contact sheet configured for %s", file_key)
        return []

    rows = _read_sheet(cfg["file"], cfg["contact_sheet"], cfg["contact_cols"],
                       cfg.get("contact_start", 3), stop_on_empty=True)
    log.info("Extracted %d contacts from %s", len(rows), file_key)
    return rows


# ── Main extract orchestrator ─────────────────────────────────────────────────

def extract_all():
    """Run all extractions for all configured files. Returns a dict of all extracted data."""
    data = {}

    for key, cfg in FILE_CONFIG.items():
        pline = key.split("_")[0]  # TG1 or TG2
        year = key.split("_")[1]

        if pline == "TG1":
            data[f"tg1_quotes_{year}"] = extract_tg1_quotes(key)
            partners = extract_partners(key)
            if partners:
                data.setdefault("tg1_partners", []).extend(partners)
            contacts = extract_tg1_contacts(key) if "contact_sheet" in cfg else []
            if contacts:
                data.setdefault("tg1_contacts", []).extend(contacts)

        elif pline == "TG2":
            headers, lines = extract_tg2_quotes(key)
            data[f"tg2_headers_{year}"] = headers
            data[f"tg2_lines_{year}"] = lines
            partners = extract_partners(key)
            if partners:
                data[f"tg2_partners_{year}"] = partners

    return data
