"""
Transform — normalize partners, statuses, values, dates.
"""
import logging
import re
import unicodedata
from datetime import datetime, date
from collections import defaultdict

from config import STATUS_MAP, COMPANY_SUFFIXES, MISSING_MARKERS

log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _strip_accents(s):
    """Remove Hungarian/accented characters → ASCII."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_name(name):
    """Normalize a company name for matching: lowercase, strip accents,
    remove punctuation & hyphens, remove company suffixes, collapse whitespace."""
    if not name:
        return ""
    s = str(name).strip().lower()
    s = _strip_accents(s)
    # Remove punctuation INCLUDING hyphens (Ceg-Nyolc == Ceg Nyolc)
    s = re.sub(r"[.,;:!?\"'()\[\]{}\-/]", " ", s)
    # Collapse whitespace BEFORE suffix removal (so $ anchors work)
    s = re.sub(r"\s+", " ", s).strip()
    # Remove company suffixes (anchored to end of string)
    for pattern in COMPANY_SUFFIXES:
        s = re.sub(pattern, "", s, flags=re.IGNORECASE)
    # Collapse whitespace again after suffix removal
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _clean_value(v):
    """Return None for missing markers, else the value."""
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        if v in MISSING_MARKERS or v == "":
            return None
    return v


def _to_iso_date(v):
    """Convert various date formats to ISO 8601 string (YYYY-MM-DD)."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, (int, float)):
        # Excel serial date — shouldn't happen with data_only=True but just in case
        return None
    s = str(v).strip()
    if s in MISSING_MARKERS:
        return None
    # Try common formats
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y.%m.%d.", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    log.warning("Could not parse date: %r", v)
    return None


def _to_float(v):
    """Convert to float or None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s in MISSING_MARKERS:
        return None
    # Handle comma decimal separator
    s = s.replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _to_int(v):
    """Convert to int or None."""
    f = _to_float(v)
    return int(f) if f is not None else None


def _reaction_days(request_date_str, sent_date_str):
    """Calendar days between request and sent dates."""
    if not request_date_str or not sent_date_str:
        return None
    try:
        d1 = datetime.strptime(request_date_str, "%Y-%m-%d")
        d2 = datetime.strptime(sent_date_str, "%Y-%m-%d")
        delta = (d2 - d1).days
        return float(delta) if delta >= 0 else None
    except ValueError:
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  Work number (munkaszám) parsing
# ══════════════════════════════════════════════════════════════════════════════

# TG2: W + 3-digit serial + 2-digit year  e.g. W90126 → year=2026, serial=901
# TG1: 2-digit year + 3-digit serial       e.g. 26902  → year=2026, serial=902
# Parts: /1, /2 or /A, /B appended        e.g. 26902/1, W90126/A

_RE_TG2_WORK = re.compile(
    r"^[Ww](\d{3})(\d{2})(?:\s*[/]?\s*([A-Za-z0-9]+))?$"
)
_RE_TG1_WORK = re.compile(
    r"^(\d{2})(\d{3})(?:\s*[/]?\s*([A-Za-z0-9]+))?$"
)


def parse_work_number(raw, product_line):
    """Parse a work number string. Returns dict with parsed fields + anomaly flag."""
    result = {
        "work_number_clean": None,
        "work_number_year": None,
        "work_number_serial": None,
        "work_number_part": None,
        "work_number_anomaly": None,
    }
    if not raw:
        return result

    s = str(raw).strip()
    if s in MISSING_MARKERS:
        return result

    result["work_number_clean"] = s

    if product_line == "TG2":
        m = _RE_TG2_WORK.match(s)
        if m:
            serial, yr, part = m.groups()
            result["work_number_year"] = 2000 + int(yr)
            result["work_number_serial"] = int(serial)
            result["work_number_part"] = part
        else:
            result["work_number_anomaly"] = f"TG2 munkaszám nem illeszkedik mintára: {s}"
    elif product_line == "TG1":
        m = _RE_TG1_WORK.match(s)
        if m:
            yr, serial, part = m.groups()
            result["work_number_year"] = 2000 + int(yr)
            result["work_number_serial"] = int(serial)
            result["work_number_part"] = part
        else:
            result["work_number_anomaly"] = f"TG1 munkaszám nem illeszkedik mintára: {s}"

    return result


def detect_crossyear(quote_year, work_number_year):
    """Return True if the work was won in a different year than the quote was issued."""
    if quote_year is None or work_number_year is None:
        return None
    return 1 if work_number_year != quote_year else 0


# ══════════════════════════════════════════════════════════════════════════════
#  Status normalization
# ══════════════════════════════════════════════════════════════════════════════

_STATUS_DICT = None  # lazy cache: admin.db status_dictionary (lowercased raw → tuple)


def load_status_dictionary(admin_db_path=None):
    """Load operator-added statuses from admin.db status_dictionary.

    The import wizard writes new raw statuses here; without this the ETL would
    still map them to NULL. Returns dict  raw_lower → (normalized, is_open, is_won, is_lost).
    """
    import sqlite3
    from config import ADMIN_DB_PATH

    path = admin_db_path or ADMIN_DB_PATH
    if not path or not path.exists():
        return {}
    conn = sqlite3.connect(str(path))
    try:
        rows = conn.execute(
            "SELECT raw_status, normalized, is_open, is_won, is_lost FROM status_dictionary"
        ).fetchall()
    except sqlite3.OperationalError as e:
        log.warning("status_dictionary unavailable (%s)", e)
        return {}
    finally:
        conn.close()
    return {str(r[0]).strip().lower(): (r[1], r[2], r[3], r[4]) for r in rows if r[0]}


def normalize_status(raw):
    """Return (normalized_status, is_open, is_won, is_lost) or log unknown.

    Lookup order: config.STATUS_MAP, then the operator status_dictionary (admin.db);
    each first exact (lowercased), then accent-stripped.
    """
    global _STATUS_DICT
    if raw is None:
        return None, 0, 0, 0
    if _STATUS_DICT is None:
        _STATUS_DICT = load_status_dictionary()
    key = str(raw).strip().lower()
    key_ascii = _strip_accents(key)
    for mapping in (STATUS_MAP, _STATUS_DICT):
        # Try exact match first
        if key in mapping:
            return mapping[key]
        # Try without accents
        for map_key, val in mapping.items():
            if _strip_accents(map_key) == key_ascii:
                return val
    log.warning("Unknown status: %r", raw)
    return None, 0, 0, 0


# ══════════════════════════════════════════════════════════════════════════════
#  Authoritative country overrides (admin.db, operator decisions)
# ══════════════════════════════════════════════════════════════════════════════

def load_country_overrides(admin_db_path=None):
    """Load authoritative MANUAL country resolutions from admin.db.

    "Country" here means *the entity we actually do business with* — a deliberate
    analytical choice for multinationals/merged groups (e.g. an Austrian contact
    of a New-York-headquartered global firm is counted as Austrian, because that
    is who we deal with and analyze). Only operator-entered *manual* resolutions
    are authoritative and override the source Excel; system-generated resolutions
    are ignored (they can be wrong, e.g. a cross-ref that picks the wrong country).
    is_domestic is DERIVED from the resolved country name — the is_domestic column
    stored in admin.db is unreliable (country was fixed without recomputing it).

    Returns: dict  name_normalized → (country, is_domestic)
    """
    import sqlite3
    from config import ADMIN_DB_PATH

    path = admin_db_path or ADMIN_DB_PATH
    overrides = {}
    if not path or not path.exists():
        log.info("No admin.db (%s) — no country overrides applied", path)
        return overrides

    conn = sqlite3.connect(str(path))
    try:
        rows = conn.execute(
            "SELECT partner_name_raw, resolved_country FROM country_resolutions "
            "WHERE resolution_method = 'manual' "
            "AND resolved_country IS NOT NULL AND TRIM(resolved_country) != ''"
        ).fetchall()
    except sqlite3.OperationalError as e:
        log.warning("country_resolutions unavailable (%s) — no overrides", e)
        return overrides
    finally:
        conn.close()

    conflicts = 0
    for raw, country in rows:
        norm = normalize_name(raw)
        if not norm:
            continue
        country = str(country).strip()
        is_dom = 1 if country.lower().startswith("magyar") else 0
        if norm in overrides and overrides[norm][0] != country:
            conflicts += 1
            log.warning("Country override conflict for %r: %s vs %s (keeping first)",
                        norm, overrides[norm][0], country)
            continue
        overrides[norm] = (country, is_dom)
    log.info("Loaded %d manual country overrides from admin.db (%d conflicts)",
             len(overrides), conflicts)
    return overrides


def load_partner_master_countries(admin_db_path=None):
    """Country base from admin.db partner_master (+ aliases): name_normalized → country.

    partner_master is the operator's curated master table (~96% country coverage).
    The standalone ETL (run_etl.py) uses this as the country base so it matches the
    coverage of the admin-wizard build (otherwise standalone would leave most
    partners' country NULL). is_domestic is DERIVED downstream from the country name.

    Returns: dict  name_normalized → country
    """
    import sqlite3
    from config import ADMIN_DB_PATH

    path = admin_db_path or ADMIN_DB_PATH
    cmap = {}
    if not path or not path.exists():
        return cmap

    conn = sqlite3.connect(str(path))
    try:
        for raw, country in conn.execute(
            "SELECT display_name, country FROM partner_master "
            "WHERE country IS NOT NULL AND TRIM(country) != ''"
        ):
            n = normalize_name(raw)
            if n:
                cmap[n] = str(country).strip()
        # Map every alias to its master's country (catches raw name variants)
        for raw, country in conn.execute(
            "SELECT a.alias_name, m.country FROM partner_aliases a "
            "JOIN partner_master m ON a.partner_id = m.partner_id "
            "WHERE m.country IS NOT NULL AND TRIM(m.country) != ''"
        ):
            n = normalize_name(raw)
            if n and n not in cmap:
                cmap[n] = str(country).strip()
    except sqlite3.OperationalError as e:
        log.warning("partner_master unavailable (%s) — no country base", e)
    finally:
        conn.close()
    log.info("Loaded %d partner_master country entries from admin.db", len(cmap))
    return cmap


# ══════════════════════════════════════════════════════════════════════════════
#  Partner normalization
# ══════════════════════════════════════════════════════════════════════════════

def build_partner_registry(data, external_lookup=None):
    """
    Build unified partner registry from all sources.
    If external_lookup is provided (admin mode), use PM-XXXX IDs from admin.db
    instead of generating P-XXXX IDs from scratch.
    external_lookup: dict  name_normalized → {"partner_id": "PM-0001", ...}
    Returns: dict  name_normalized → partner_dict
    """
    if external_lookup:
        return _build_partner_registry_admin(data, external_lookup)
    # Collect all unique partner names from every source
    all_names = {}  # normalized_name → set of raw names

    def _add(name, source):
        if not name:
            return
        raw = str(name).strip()
        norm = normalize_name(raw)
        if not norm:
            return
        if norm not in all_names:
            all_names[norm] = {"raws": set(), "sources": set()}
        all_names[norm]["raws"].add(raw)
        all_names[norm]["sources"].add(source)

    # From quote tables (dynamic years)
    for key, val in data.items():
        if key.startswith("tg1_quotes_"):
            for r in val:
                _add(r.get("partner_name"), "TG1")
        elif key.startswith("tg2_headers_"):
            for r in val:
                _add(r.get("partner_name"), "TG2")

    # From partner lists (dynamic years)
    for r in data.get("tg1_partners", []):
        _add(r.get("name"), "TG1")
    for key, val in data.items():
        if key.startswith("tg2_partners_"):
            for r in val:
                _add(r.get("name"), "TG2")

    # Build TG1 partner lookup for enrichment (by normalized name)
    tg1_partner_lookup = {}
    for r in data.get("tg1_partners", []):
        name = r.get("name")
        if name:
            norm = normalize_name(name)
            tg1_partner_lookup[norm] = r

    # Build TG2 partner lookup for country enrichment
    tg2_partner_lookup = {}
    for r in data.get("tg2_partners_2025", []) + data.get("tg2_partners_2026", []):
        name = r.get("name")
        if name:
            norm = normalize_name(name)
            if norm not in tg2_partner_lookup:  # prefer 2025 (more complete)
                tg2_partner_lookup[norm] = r

    # Fuzzy matching for remaining unmatched names
    redirect_map = _try_fuzzy_merge(all_names)

    # Authoritative country base from admin.db partner_master (~96% coverage).
    # Mirrors the admin-wizard build so standalone run_etl.py doesn't lose country.
    pm_countries = load_partner_master_countries()

    # Generate partner records
    partners = {}
    pid_counter = 1
    for norm, info in sorted(all_names.items()):
        pid = f"P-{pid_counter:04d}"
        pid_counter += 1

        # Pick the longest raw name as the display name
        raw_names = sorted(info["raws"], key=len, reverse=True)
        display_name = raw_names[0]

        sources = info["sources"]
        if "TG1" in sources and "TG2" in sources:
            source = "mindkettő"
        elif "TG1" in sources:
            source = "TG1"
        else:
            source = "TG2"

        p = {
            "partner_id": pid,
            "name": display_name,
            "name_normalized": norm,
            "official_name": None,
            "tax_id": None,
            "country": None,
            "is_domestic": None,
            "partner_type": None,
            "industry": None,
            "teaor_code": None,
            "first_contact_date": None,
            "source": source,
        }

        # Enrich from TG1 partner list
        tg1 = tg1_partner_lookup.get(norm)
        if tg1:
            p["official_name"] = _clean_value(tg1.get("official_name"))
            p["tax_id"] = _clean_value(tg1.get("tax_id"))
            p["country"] = _clean_value(tg1.get("country"))
            p["partner_type"] = _clean_value(tg1.get("partner_type"))
            p["industry"] = _clean_value(tg1.get("teaor_name"))
            p["teaor_code"] = _clean_value(tg1.get("teaor_code"))
            p["first_contact_date"] = _to_iso_date(tg1.get("first_contact_date"))
            if p["country"]:
                p["is_domestic"] = 1 if p["country"].lower().startswith("magyar") else 0

        # If no country from TG1, try TG2 partner list
        if p["country"] is None:
            tg2 = tg2_partner_lookup.get(norm)
            if tg2:
                p["country"] = _clean_value(tg2.get("country"))
                if p["first_contact_date"] is None:
                    p["first_contact_date"] = _to_iso_date(tg2.get("first_contact_date"))

        # partner_master (admin.db) is the authoritative country base — it takes
        # precedence over Excel partner-sheet country (mirrors the admin build).
        if pm_countries.get(norm):
            p["country"] = pm_countries[norm]
        # Derive is_domestic from the final country (stored flags are unreliable)
        if p["country"]:
            p["is_domestic"] = 1 if str(p["country"]).lower().startswith("magyar") else 0

        partners[norm] = p

    # Add redirect aliases so quote lookups for merged keys still work
    for old_key, new_key in redirect_map.items():
        if new_key in partners and old_key not in partners:
            partners[old_key] = partners[new_key]

    log.info("Built partner registry: %d unique partners (%d with aliases)",
             len(partners) - len(redirect_map), len(partners))
    return partners


def _build_partner_registry_admin(data, external_lookup):
    """Build partner registry using admin-resolved PM-XXXX IDs.
    external_lookup: dict  name_normalized → partner_dict with partner_id, etc.
    """
    # Collect all unique normalized names from the data (dynamic years)
    all_norms = set()
    for key, val in data.items():
        if key.startswith("tg1_quotes_") or key.startswith("tg2_headers_"):
            for r in val:
                n = normalize_name(r.get("partner_name"))
                if n:
                    all_norms.add(n)

    # Build country lookup from raw quote data (TG2 has country in column F, TG1 has country_name)
    country_by_norm = {}
    for key, val in data.items():
        if key.startswith("tg2_headers_"):
            for r in val:
                n = normalize_name(r.get("partner_name"))
                c = r.get("country")
                if n and c and str(c).strip():
                    country_by_norm.setdefault(n, str(c).strip())
        elif key.startswith("tg1_quotes_"):
            for r in val:
                n = normalize_name(r.get("partner_name"))
                c = r.get("country_name")
                if n and c and str(c).strip():
                    country_by_norm.setdefault(n, str(c).strip())

    # Build the registry from external_lookup, enriched with quote-level country
    partners = {}
    unmatched = 0
    for norm in all_norms:
        if norm in external_lookup:
            p = dict(external_lookup[norm])  # copy so we don't mutate the lookup
            # Enrich with country from raw data if partner_master has none
            if not p.get("country") and norm in country_by_norm:
                p["country"] = country_by_norm[norm]
                p["is_domestic"] = 1 if p["country"].lower().startswith("magyar") else 0
            partners[norm] = p
        else:
            # Shouldn't happen if admin wizard resolved everything, but log it
            log.warning("Admin mode: no external match for %r", norm)
            unmatched += 1

    if unmatched:
        log.warning("Admin mode: %d unmatched partner names", unmatched)
    log.info("Admin partner registry: %d partners from external lookup", len(partners))
    return partners


def _try_fuzzy_merge(all_names):
    """Merge names that are very similar (SequenceMatcher ratio >= 0.92).
    Modifies all_names in place by merging similar entries.
    Returns a redirect map: deleted_key → surviving_key (for quote lookups).
    Only considers names with >= 6 characters (short names produce too many false positives)."""
    from difflib import SequenceMatcher

    keys = sorted(all_names.keys())
    merged = {}  # k2 → k1 (redirect map)
    for i, k1 in enumerate(keys):
        if k1 in merged or len(k1) < 6:
            continue
        for k2 in keys[i + 1:]:
            if k2 in merged or len(k2) < 6:
                continue
            # Quick length check — skip if lengths differ too much
            if abs(len(k1) - len(k2)) > max(len(k1), len(k2)) * 0.15:
                continue
            ratio = SequenceMatcher(None, k1, k2).ratio()
            if ratio >= 0.92:
                log.info("Fuzzy merge: %r ↔ %r (%.0f%%)", k1, k2, ratio * 100)
                # Merge k2 into k1
                all_names[k1]["raws"].update(all_names[k2]["raws"])
                all_names[k1]["sources"].update(all_names[k2]["sources"])
                merged[k2] = k1

    for k in merged:
        del all_names[k]

    if merged:
        log.info("Fuzzy merged %d partner name variants", len(merged))

    return merged


# ══════════════════════════════════════════════════════════════════════════════
#  Quote normalization
# ══════════════════════════════════════════════════════════════════════════════

def transform_tg1_quotes(raw_quotes, partner_lookup, country_overrides=None):
    """Transform TG1 quote rows into normalized quote dicts."""
    quotes = []
    for r in raw_quotes:
        qid = str(r["quote_id"]).strip()
        partner_raw = _clean_value(r.get("partner_name"))
        partner_norm = normalize_name(partner_raw) if partner_raw else ""
        partner = partner_lookup.get(partner_norm, {})

        status_raw = _clean_value(r.get("status"))
        norm_status, is_open, is_won, is_lost = normalize_status(status_raw)

        request_date = _to_iso_date(r.get("request_date"))
        sent_date = _to_iso_date(r.get("sent_date"))

        # Country: try quote-level first, then partner-level
        country_name = _clean_value(r.get("country_name"))
        country_domestic = _clean_value(r.get("country_domestic"))
        if not country_name:
            country_name = partner.get("country")

        # is_domestic is DERIVED from the country name; the belföldi/külföldi
        # flag column is only a fallback (it contradicts the name in places)
        if country_name:
            is_dom = 1 if str(country_name).lower().startswith("magyar") else 0
        elif country_domestic:
            is_dom = 1 if str(country_domestic).lower().startswith("belf") else 0
        else:
            is_dom = None

        # Authoritative manual override (admin.db) wins over the source value
        if country_overrides and partner_norm in country_overrides:
            country_name, is_dom = country_overrides[partner_norm]

        wn_raw = _clean_value(r.get("work_number"))
        wn = parse_work_number(wn_raw, "TG1")

        q = {
            "quote_id": qid,
            "product_line": r["product_line"],
            "year": r["year"],
            "partner_id": partner.get("partner_id"),
            "partner_name_raw": partner_raw,
            "subject": _clean_value(r.get("subject")),
            "handler_name": _clean_value(r.get("handler_name")),
            "handler_email": _clean_value(r.get("handler_email")),
            "request_date": request_date,
            "deadline_date": _to_iso_date(r.get("deadline_date")),
            "sent_date": sent_date,
            "close_date": None,
            "status_raw": status_raw,
            "status": norm_status,
            "registry_number": _clean_value(r.get("registry_number")),
            "revision": _clean_value(r.get("revision")),
            "total_value_eur": _to_float(r.get("total_value_eur")),
            "work_number": wn_raw,
            "work_number_year": wn["work_number_year"],
            "work_number_part": wn["work_number_part"],
            "is_crossyear": detect_crossyear(r["year"], wn["work_number_year"]),
            "work_number_anomaly": wn["work_number_anomaly"],
            "country": country_name,
            "is_domestic": is_dom,
            "loss_reason": None,
            "reaction_days": None,
        }
        # Reaction days only for base RFQ (TG1: REV0 = first issue)
        rev = _clean_value(r.get("revision"))
        if rev is None or str(rev).strip().upper() == "REV0":
            q["reaction_days"] = _reaction_days(request_date, sent_date)

        quotes.append(q)
    return quotes


def transform_tg2_quotes(headers, line_items, partner_lookup, country_overrides=None):
    """Transform TG2 headers + line items into normalized quotes and quote_lines."""
    quotes = []
    q_lines = []

    # Group line items by quote_id for value aggregation
    lines_by_qid = defaultdict(list)
    for li in line_items:
        qid = str(li["quote_id"]).strip()
        lines_by_qid[qid].append(li)

    # Also collect first-row line items (header rows are also line items with POS)
    for h in headers:
        qid = str(h["quote_id"]).strip()
        partner_raw = _clean_value(h.get("partner_name"))
        partner_norm = normalize_name(partner_raw) if partner_raw else ""
        partner = partner_lookup.get(partner_norm, {})

        status_raw = _clean_value(h.get("status"))
        norm_status, is_open, is_won, is_lost = normalize_status(status_raw)

        request_date = _to_iso_date(h.get("request_date"))
        sent_date = _to_iso_date(h.get("sent_date"))

        country_name = _clean_value(h.get("country"))
        if not country_name:
            country_name = partner.get("country")
        is_dom = None
        if country_name:
            is_dom = 1 if str(country_name).lower().startswith("magyar") else 0

        # Authoritative manual override (admin.db) wins over the source value
        if country_overrides and partner_norm in country_overrides:
            country_name, is_dom = country_overrides[partner_norm]

        # Revision: TG2 stores as integer (0, 1, 2...), convert to REV format
        rev_raw = h.get("revision")
        revision = f"REV{int(rev_raw)}" if _to_int(rev_raw) is not None else None

        # Aggregate total value: header POS value + all line item values
        header_val = _to_float(h.get("line_value_eur"))
        line_vals = [_to_float(li.get("line_value_eur")) for li in lines_by_qid.get(qid, [])]
        all_vals = [v for v in [header_val] + line_vals if v is not None]
        total_value = sum(all_vals) if all_vals else None

        wn_raw = _clean_value(h.get("work_number"))
        wn = parse_work_number(wn_raw, "TG2")

        q = {
            "quote_id": qid,
            "product_line": h["product_line"],
            "year": h["year"],
            "partner_id": partner.get("partner_id"),
            "partner_name_raw": partner_raw,
            "subject": _clean_value(h.get("subject")),
            "handler_name": _clean_value(h.get("handler_name")),
            "handler_email": _clean_value(h.get("handler_email")),
            "request_date": request_date,
            "deadline_date": None,
            "sent_date": sent_date,
            "close_date": None,
            "status_raw": status_raw,
            "status": norm_status,
            "registry_number": _clean_value(h.get("registry_number")),
            "revision": revision,
            "total_value_eur": total_value,
            "work_number": wn_raw,
            "work_number_year": wn["work_number_year"],
            "work_number_part": wn["work_number_part"],
            "is_crossyear": detect_crossyear(h["year"], wn["work_number_year"]),
            "work_number_anomaly": wn["work_number_anomaly"],
            "country": country_name,
            "is_domestic": is_dom,
            "loss_reason": None,
            "reaction_days": None,
        }
        # Reaction days only for base RFQ (TG2: REV1 = first issue, sorszám 1)
        if revision is None or revision == "REV1":
            q["reaction_days"] = _reaction_days(request_date, sent_date)

        quotes.append(q)

        # Build line items: header's own POS + additional line items
        all_line_rows = [h] + lines_by_qid.get(qid, [])
        for li in all_line_rows:
            pos = _to_int(li.get("position"))
            if pos is None:
                continue
            ql = {
                "quote_id": qid,
                "position": pos,
                "quantity": _to_int(li.get("quantity")),
                "unit_price_eur": _to_float(li.get("unit_price_eur")),
                "line_value_eur": _to_float(li.get("line_value_eur")),
                "product_type": _clean_value(li.get("product_type")),
                "material": _clean_value(li.get("material")),
                "size_param": _to_float(li.get("size_param")),
                "status_raw": _clean_value(li.get("status")),
            }
            q_lines.append(ql)

    return quotes, q_lines


# ══════════════════════════════════════════════════════════════════════════════
#  Status map table
# ══════════════════════════════════════════════════════════════════════════════

def build_status_map():
    """Build list of status_map rows for the status_map table."""
    seen = {}
    for raw, (norm, is_open, is_won, is_lost) in STATUS_MAP.items():
        if norm not in seen:
            seen[norm] = {"raw_statuses": [], "normalized_status": norm,
                          "is_open": is_open, "is_won": is_won, "is_lost": is_lost}
        seen[norm]["raw_statuses"].append(raw)

    rows = []
    for raw, (norm, is_open, is_won, is_lost) in STATUS_MAP.items():
        rows.append({
            "raw_status": raw,
            "normalized_status": norm,
            "is_open": is_open,
            "is_won": is_won,
            "is_lost": is_lost,
        })
    return rows


# ══════════════════════════════════════════════════════════════════════════════
#  Main transform orchestrator
# ══════════════════════════════════════════════════════════════════════════════

def transform_all(data, external_lookup=None):
    """Run all transformations. Returns normalized data dict.
    If external_lookup is provided (admin mode), use PM-XXXX IDs from admin.db.
    """
    result = {}

    # 1. Build partner registry (includes aliases for fuzzy-merged keys)
    partners = build_partner_registry(data, external_lookup=external_lookup)

    # Authoritative manual country overrides from admin.db (the "who we deal
    # with" analytical choice). Applied to partners here and to quotes below.
    country_overrides = load_country_overrides()
    for _norm, (_country, _isdom) in country_overrides.items():
        p = partners.get(_norm)
        if p is not None:
            p["country"] = _country
            p["is_domestic"] = _isdom

    # Deduplicate for DB insert (aliases share the same partner_id)
    seen_pids = set()
    unique_partners = []
    for p in partners.values():
        if p["partner_id"] not in seen_pids:
            seen_pids.add(p["partner_id"])
            unique_partners.append(p)
    result["partners"] = unique_partners

    # 2. Transform TG1 quotes (dynamic years)
    result["quotes"] = []
    for key, val in data.items():
        if key.startswith("tg1_quotes_"):
            result["quotes"] += transform_tg1_quotes(val, partners, country_overrides)

    # 3. Transform TG2 quotes + line items (dynamic years)
    result["quote_lines"] = []
    for key, val in data.items():
        if key.startswith("tg2_headers_"):
            year = key.replace("tg2_headers_", "")
            lines = data.get(f"tg2_lines_{year}", [])
            eq, el = transform_tg2_quotes(val, lines, partners, country_overrides)
            result["quotes"] += eq
            result["quote_lines"] += el

    # 4. Deduplicate quotes by quote_id (prefer later year if duplicate)
    seen_ids = {}
    deduped = []
    for q in result["quotes"]:
        qid = q["quote_id"]
        if qid in seen_ids:
            existing = seen_ids[qid]
            # Keep the one with more recent data (higher year, or non-null status)
            if q["year"] > existing["year"]:
                deduped[deduped.index(existing)] = q
                seen_ids[qid] = q
                log.info("Dedup: %s — kept year %d over %d", qid, q["year"], existing["year"])
        else:
            seen_ids[qid] = q
            deduped.append(q)
    result["quotes"] = deduped

    # 5. Enrich first_contact_date from MIN(request_date) per partner
    _enrich_first_contact(result["partners"], result["quotes"])

    # 6. Build partner_aliases table (all raw name variants per partner)
    result["partner_aliases"] = _build_alias_table(partners)

    # 7. Collect anomalies
    result["anomalies"] = _collect_anomalies(result["quotes"], result["partners"])

    # 8. Status map
    result["status_map"] = build_status_map()

    # Summary
    log.info("Transform complete: %d partners, %d quotes, %d quote lines, %d anomalies",
             len(result["partners"]), len(result["quotes"]),
             len(result["quote_lines"]), len(result["anomalies"]))

    return result


def _enrich_first_contact(partners, quotes):
    """Fill in first_contact_date from MIN(request_date) across all quotes per partner."""
    # Build min request_date per partner_id
    min_dates = {}
    for q in quotes:
        pid = q.get("partner_id")
        rd = q.get("request_date")
        if pid and rd:
            if pid not in min_dates or rd < min_dates[pid]:
                min_dates[pid] = rd

    enriched = 0
    for p in partners:
        pid = p["partner_id"]
        quote_min = min_dates.get(pid)
        if p["first_contact_date"] is None and quote_min:
            p["first_contact_date"] = quote_min
            enriched += 1
        elif p["first_contact_date"] and quote_min and quote_min < p["first_contact_date"]:
            # Quote predates partner list entry — use earlier date
            p["first_contact_date"] = quote_min
            enriched += 1

    if enriched:
        log.info("Enriched first_contact_date for %d partners from quote request dates", enriched)


def _build_alias_table(partners_dict):
    """Build partner_aliases: list of (partner_id, raw_name) for all name variants."""
    # partners_dict is keyed by normalized name, but aliases point to same partner
    seen = set()
    aliases = []
    for norm, p in partners_dict.items():
        pid = p["partner_id"]
        key = (pid, norm)
        if key not in seen:
            seen.add(key)
            aliases.append({"partner_id": pid, "alias_name": p["name"],
                            "name_normalized": norm})
    return aliases


def _collect_anomalies(quotes, partners):
    """Collect data quality anomalies for the worksheet."""
    anomalies = []

    for q in quotes:
        # Work number anomalies
        wna = q.get("work_number_anomaly")
        if wna:
            anomalies.append({
                "type": "work_number",
                "quote_id": q["quote_id"],
                "detail": wna,
            })

        # WON but no work number
        if q["status"] == "WON" and not q.get("work_number"):
            anomalies.append({
                "type": "missing_work_number",
                "quote_id": q["quote_id"],
                "detail": f"{q['quote_id']}: státusz WON de nincs munkaszám",
            })

        # Cross-year quotes
        if q.get("is_crossyear") == 1:
            anomalies.append({
                "type": "crossyear",
                "quote_id": q["quote_id"],
                "detail": (f"{q['quote_id']} (év: {q['year']}) → munkaszám év: "
                           f"{q.get('work_number_year')} — áthúzódó ügylet"),
            })

        # Missing request date
        if q.get("request_date") is None and q["status"] not in ("NO_QUOTE", "NOT_RELEVANT"):
            anomalies.append({
                "type": "missing_date",
                "quote_id": q["quote_id"],
                "detail": f"{q['quote_id']}: nincs ajánlatkérés dátum",
            })

        # Negative or extreme reaction days
        rd = q.get("reaction_days")
        if rd is not None and rd > 90:
            anomalies.append({
                "type": "slow_reaction",
                "quote_id": q["quote_id"],
                "detail": f"{q['quote_id']}: reakcióidő {int(rd)} nap (>90)",
            })

    # Partner anomalies
    for p in partners:
        if p.get("country") is None:
            anomalies.append({
                "type": "missing_country",
                "quote_id": None,
                "detail": f"Partner {p['partner_id']} ({p['name']}): nincs ország",
            })

    return anomalies
