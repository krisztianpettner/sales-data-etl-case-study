#!/usr/bin/env python3
"""
Read-only extractor + reconciler for the rendelesi_regiszter (order register / főregiszter).

Cleans the messy sheet, applies the business rules, ACCRUES order value per register year
(időbeli elhatárolás), loads a `work_orders` table + views into etl/dashboard.db, and emits
an order-driven hibalista. Read-only w.r.t. the Excel sources.

Business rules (confirmed with the user):
  * Column A = MSZ (join key), B = type (E=TG1 / TG2 / S=termékcsoport3).
  * S (3rd division) is EXCLUDED. Consistency: after removing S, no 4-digit MSZ remains.
  * B is section-based & sparse -> forward-fill last valid B. Any E-prefixed MSZ is TG2.
  * Sub-numbers (/1 /2 /A ...) -> strip part, aggregate K/P onto the base order.
  * SAJÁT GYÁRTÁS (own production): customer = MEGBÍZÓ -> internal termékcsoport2 for our own termék;
    revenue is on the TG1 product, so EXCLUDED from the TG2 SoT. Decided at ORDER level: if ANY part
    of an MSZ is MEGBÍZÓ, the whole MSZ is saját (catches blank-customer carry rows, e.g. W90126/I).
    Mirrored on the quote side (MEGBÍZÓ→MEGBÍZÓ quotes dropped) — we don't quote to ourselves.
  * ELHATÁROLÁS / accrual: a multi-year order's MSZ recurs in several years' registers, each with
    THAT year's amount, booked to THAT year. -> NO dedup: one work_orders row per (MSZ, register
    year); EUR SoT by year = SUM of that year's amounts; order value spans years.
  * EUR SoT = K (Teljesítési, vállalási ár EUR); fall back to P (Számlázott EUR, NOT Q/HUF) when
    K is empty or 0. Join to quotes on parsed (product_line, work_number_year, serial).
"""
import csv
import os
import re
import sqlite3
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "etl"))
from transform import parse_work_number, normalize_name  # reuse canonical parser + name matcher

DATA = os.path.join(ROOT, "data")
DB = os.path.join(ROOT, "etl", "dashboard.db")
SHEET = "Rendelési regiszter"
FILE_YEARS = (2023, 2024, 2025, 2026)

# Column indices (0-based) in the Rendelési regiszter sheet
C_MSZ, C_TYPE, C_CUST, C_DESC = 0, 1, 2, 3
C_PV = 5
C_ORDER_DATE = 7
C_K_EUR = 10          # Teljesítési összeg, vállalási ár (EUR)  -> EUR SoT
C_P_EUR = 15          # Számlázott összeg N°(EUR)               -> fallback when K is 0/empty
# C_Q_HUF = 16        # Számlázott összeg N°(Ft) — HUF, deliberately NOT used (SoT is EUR)


def _to_float(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v)).replace(",", ".")
    try:
        return float(s) if s not in ("", ".", "-") else None
    except ValueError:
        return None


def strip_part(raw):
    """Drop the /1 /2 /A part and -USA region suffix -> base MSZ string."""
    s = re.sub(r"\s+", "", str(raw).strip())
    s = re.sub(r"/.*$", "", s)
    s = re.sub(r"-(USA|EU|HU|DE|[A-Za-z]{2,4})$", "", s, flags=re.I)
    return s


def is_real_msz(base):
    return bool(re.match(r"^[Ww]?\d{2,6}[A-Za-z]?$", base)) and base.upper() != "MSZ"


def is_self(customer):
    """Saját gyártás: we are the customer (MEGBÍZÓ)."""
    return "megbizo" in normalize_name(customer or "")


def extract_rows():
    """Yield cleaned register rows (parts not yet aggregated), tagged by division."""
    import openpyxl
    out = []
    for fy in FILE_YEARS:
        path = os.path.join(DATA, f"rendelesi_regiszter_{fy}.xlsx")
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[SHEET]
        cur_type = None  # forward-fill state
        for row in ws.iter_rows(min_row=3, values_only=True):
            a = row[C_MSZ]
            braw = (str(row[C_TYPE]).strip() if row[C_TYPE] else "").upper()
            if braw in ("E", "TG2", "S"):
                cur_type = braw
            if a is None or str(a).strip() == "":
                continue
            base = strip_part(a)
            if not is_real_msz(base):
                continue  # noise: header / section / summary / comment rows
            customer = str(row[C_CUST]).strip() if row[C_CUST] else ""
            typ = "TG2" if re.match(r"^[Ww]\d", base) else cur_type
            if typ is None:
                continue
            if is_self(customer):
                division = "SELF"
            elif typ == "TG2":
                division = "TG2"
            elif typ == "S":
                division = "S"
            else:
                division = "TG1"
            out.append({
                "file_year": fy,
                "raw_msz": str(a).strip(),
                "base": base.upper(),
                "division": division,
                "customer": customer,
                "k_eur": _to_float(row[C_K_EUR]),
                "p_eur": _to_float(row[C_P_EUR]),
            })
        wb.close()
    return out


def canonical_key(base):
    """(pl, year, serial) from the base MSZ via the shared parser; None if it doesn't parse.
    product line is derived from the MSZ shape (E-prefix => TG2), not from a column."""
    pl = "TG2" if re.match(r"^[Ww]\d", base) else "TG1"
    p = parse_work_number(base, pl)
    if p["work_number_year"] is None or p["work_number_serial"] is None:
        return None
    return (pl, p["work_number_year"], p["work_number_serial"])


def canon_msz(key):
    pl, yr, serial = key
    return f"E{serial:03d}{yr % 100:02d}" if pl == "TG2" else f"{yr % 100:02d}{serial:03d}"


def aggregate(rows):
    """Accrual model: one record per (MSZ, register year). Returns (order_years, parse_fails).
    Group-level SELF: if ANY part of an MSZ is saját (MEGBÍZÓ), the whole MSZ is excluded."""
    self_keys = {canonical_key(r["base"]) for r in rows if r["division"] == "SELF"}
    self_keys.discard(None)
    work = [r for r in rows if r["division"] not in ("S", "SELF")]
    parse_fails = [r for r in work if canonical_key(r["base"]) is None]
    groups = defaultdict(list)
    for r in work:
        k = canonical_key(r["base"])
        if k is None or k in self_keys:
            continue
        groups[(k, r["file_year"])].append(r)
    order_years = []
    for (k, fy), grp in groups.items():
        pl, yr, serial = k
        ksum = sum(g["k_eur"] for g in grp if g["k_eur"]) or None
        psum = sum(g["p_eur"] for g in grp if g["p_eur"]) or None
        val = ksum if ksum else psum
        if not val:
            continue  # no accrual this year (tracking-only re-list) — nothing to book
        order_years.append({
            "key": k, "canonical_msz": canon_msz(k), "product_line": pl,
            "register_year": fy, "wn_year": yr, "serial": serial,
            "customer": next((g["customer"] for g in grp if g["customer"]), ""),
            "value_eur": val, "k_eur": ksum, "p_eur": psum, "n_parts": len(grp),
        })
    return order_years, parse_fails


def s_keys_of(rows):
    """Canonical keys of termékcsoport3(S) rows — to flag TG1-quote ↔ register-termékcsoport3 items."""
    return {canonical_key(r["base"]) for r in rows if r["division"] == "S"} - {None}



def aggregate_s(rows):
    """Termékcsoport3 (S) rows: one record per (base MSZ, register year), K↘P value.
    Kept OUT of the quote reconciliation (no RFQ) but loaded as product_line='S' so the
    third division is queryable (bank report §5, dashboard realized layer)."""
    groups = defaultdict(list)
    for r in rows:
        if r["division"] == "S":
            groups[(r["base"], r["file_year"])].append(r)
    out = []
    for (base, fy), grp in groups.items():
        ksum = sum(g["k_eur"] for g in grp if g["k_eur"]) or None
        psum = sum(g["p_eur"] for g in grp if g["p_eur"]) or None
        val = ksum if ksum else psum
        if not val:
            continue
        out.append({
            "key": None, "canonical_msz": base, "product_line": "S",
            "register_year": fy, "wn_year": None, "serial": None,
            "customer": next((g["customer"] for g in grp if g["customer"]), ""),
            "value_eur": val, "k_eur": ksum, "p_eur": psum, "n_parts": len(grp),
        })
    return out


# Register customer names that don't match any partner master/alias — the country is
# unambiguous from the name itself (town / "Hungary" / explicit country suffix).
_CUSTOMER_COUNTRY_HINTS = {
    # (real customer → country hints removed from the case-study copy)
}


def build_customer_resolver(db):
    """customer name → (country, is_domestic) using, in priority order: manual country
    resolutions (admin.db), dashboard partners + aliases, admin partner_master + aliases,
    name hints, and finally a 2-token prefix match. Returns a function."""
    exact = {}
    admin_db = os.path.join(ROOT, "admin", "admin.db")
    c = sqlite3.connect(db)
    for nn, co, d in c.execute("SELECT name_normalized, country, is_domestic FROM partners WHERE country IS NOT NULL AND country<>''"):
        if nn: exact.setdefault(nn, (co, d))
    for nn, co, d in c.execute("SELECT a.name_normalized, p.country, p.is_domestic FROM partner_aliases a JOIN partners p USING(partner_id) WHERE p.country IS NOT NULL AND p.country<>''"):
        if nn: exact.setdefault(nn, (co, d))
    c.close()
    if os.path.exists(admin_db):
        a = sqlite3.connect(admin_db)
        for nn, co in a.execute("SELECT name_normalized, country FROM partner_master WHERE country IS NOT NULL AND country<>''"):
            exact.setdefault(nn, (co, 1 if co == "Magyarország" else 0))
        for nn, co in a.execute("SELECT al.name_normalized, p.country FROM partner_aliases al JOIN partner_master p USING(partner_id) WHERE p.country IS NOT NULL AND p.country<>''"):
            exact.setdefault(nn, (co, 1 if co == "Magyarország" else 0))
        for nn, co in a.execute("SELECT partner_name_normalized, resolved_country FROM country_resolutions WHERE resolution_method='manual' AND resolved_country IS NOT NULL"):
            exact[nn] = (co, 1 if co == "Magyarország" else 0)   # manual wins
        a.close()
    prefix_index = {}
    for nn, v in exact.items():
        toks = nn.split()
        if len(toks) >= 2:
            prefix_index.setdefault(" ".join(toks[:2]), v)

    def resolve(customer):
        nn = normalize_name(customer or "")
        if not nn:
            return (None, None)
        if nn in exact:
            return exact[nn]
        if nn in _CUSTOMER_COUNTRY_HINTS:
            return _CUSTOMER_COUNTRY_HINTS[nn]
        toks = nn.split()
        if len(toks) >= 2 and " ".join(toks[:2]) in prefix_index:
            return prefix_index[" ".join(toks[:2])]
        return (None, None)
    return resolve


def load_quote_groups():
    """Quotes from dashboard.db, parsed to (pl, year, serial). Saját (MEGBÍZÓ) quotes dropped.
    On work_number collisions (several quote rows / partners share an MSZ) a WON row is preferred,
    and collisions across DIFFERENT partners are reported (data error: wrong MSZ on a quote).
    Returns (groups, parse_fails, collisions)."""
    c = sqlite3.connect(DB)
    q = c.execute("SELECT product_line, work_number, status, total_value_eur, partner_name_raw, "
                  "registry_number, quote_id FROM quotes "
                  "WHERE work_number IS NOT NULL AND TRIM(work_number)<>''").fetchall()
    c.close()
    raw, fails = defaultdict(list), []
    for pl, wn, status, val, partner, registry, qid in q:
        if is_self(partner):
            continue  # saját gyártás — not a market quote
        key = canonical_key(strip_part(str(wn)))
        if key is None:
            fails.append((pl, wn, status))
            continue
        raw[key].append({"product_line": pl, "work_number": wn, "status": status, "value": val,
                         "partner": partner or "", "registry": registry or "", "quote_id": qid or ""})
    groups, collisions = {}, []
    for key, lst in raw.items():
        won = [x for x in lst if x["status"] == "WON"]
        groups[key] = won[0] if won else lst[0]      # prefer a WON row
        if len({normalize_name(x["partner"]) for x in lst}) > 1:
            collisions.append((key, lst))             # same MSZ, different partners -> data error
    return groups, fails, collisions


# ── reconciliation / output helpers ────────────────────────────────────────────

def quote_partner_index(db):
    c = sqlite3.connect(db)
    rows = c.execute("SELECT partner_name_raw, status, work_number, year FROM quotes").fetchall()
    c.close()
    idx = defaultdict(list)
    for partner, st, wn, yr in rows:
        idx[normalize_name(partner or "")].append((st, (wn or "").strip(), yr))
    return idx


def triage_orphan(customer, qidx):
    """An MSZ-less quote is NORMAL for a non-won RFQ — only a WON quote without a work number
    is a real data-entry gap. Returns (category, action)."""
    cands = qidx.get(normalize_name(customer), [])
    if [q for q in cands if q[0] == "WON" and not q[1]]:
        return "① WON ajánlat MSZ nélkül", "írd be a munkaszámot a nyertes ajánlatba"
    if cands:
        return "② csak el-nem-nyert / MSZ-es ajánlat", "ellenőrzés (lehet el-nem-nyert RFQ; névösszevonás után újra)"
    return "③ nincs ajánlat", "valódi RFQ-hiány — nézd meg, van-e ajánlat más néven"


def write_xlsx(cols, rows, path, widths=None):
    import openpyxl
    from openpyxl.styles import Font
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "hibalista"
    ws.append(cols)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for r in rows:
        ws.append(r)
    for col, wd in zip("ABCDEFGH", widths or []):
        ws.column_dimensions[col].width = wd
    wb.save(path)


def load_to_db(order_years, s_years, quotes, db, meta=None):
    """Write the work_orders table (one row per MSZ×register year, TG1/TG2/S) + views into
    dashboard.db. Customer country/is_domestic resolved against the partner master."""
    resolve = build_customer_resolver(db)
    c = sqlite3.connect(db)
    cur = c.cursor()
    cur.execute("DROP VIEW IF EXISTS v_work_reconciliation")
    cur.execute("DROP VIEW IF EXISTS v_work_orders_eur")
    cur.execute("DROP TABLE IF EXISTS work_orders")
    cur.execute("DROP TABLE IF EXISTS work_orders_meta")
    cur.execute("""CREATE TABLE work_orders (
        canonical_msz TEXT, product_line TEXT, register_year INTEGER, wn_year INTEGER,
        serial INTEGER, customer TEXT, value_eur REAL, k_eur REAL, p_eur REAL, n_parts INTEGER,
        has_quote INTEGER, quote_status TEXT, country TEXT, is_domestic INTEGER)""")
    n_na = 0
    for o in order_years + s_years:
        q = quotes.get(o["key"]) if o["key"] else None
        co, d = resolve(o["customer"])
        if d is None:
            n_na += 1
        cur.execute("INSERT INTO work_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            o["canonical_msz"], o["product_line"], o["register_year"], o["wn_year"], o["serial"],
            o["customer"], o["value_eur"], o["k_eur"], o["p_eur"], o["n_parts"],
            1 if q else 0, q["status"] if q else None, co, d))
    cur.execute("""CREATE VIEW v_work_orders_eur AS
        SELECT product_line, register_year AS year, COUNT(*) AS order_years,
               COUNT(DISTINCT canonical_msz) AS distinct_msz, ROUND(SUM(value_eur), 0) AS eur_sot,
               ROUND(SUM(CASE WHEN is_domestic = 1 THEN value_eur ELSE 0 END), 0) AS eur_magyar,
               ROUND(SUM(CASE WHEN is_domestic = 0 THEN value_eur ELSE 0 END), 0) AS eur_kulfoldi,
               ROUND(SUM(CASE WHEN is_domestic IS NULL THEN value_eur ELSE 0 END), 0) AS eur_besorolatlan
        FROM work_orders GROUP BY product_line, register_year""")
    cur.execute("""CREATE VIEW v_work_reconciliation AS
        SELECT product_line, register_year AS year, ROUND(SUM(value_eur), 0) AS eur,
               ROUND(SUM(CASE WHEN has_quote = 1 THEN value_eur ELSE 0 END), 0) AS eur_van_quote,
               ROUND(SUM(CASE WHEN has_quote = 0 THEN value_eur ELSE 0 END), 0) AS eur_nincs_quote
        FROM work_orders WHERE product_line IN ('TG1','TG2') GROUP BY product_line, register_year""")
    cur.execute("CREATE TABLE work_orders_meta (key TEXT PRIMARY KEY, value TEXT)")
    meta = dict(meta or {})
    meta["loaded_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    meta["customer_unresolved_rows"] = n_na
    for k, v in meta.items():
        cur.execute("INSERT INTO work_orders_meta VALUES (?,?)", (k, str(v)))
    c.commit()
    c.close()


def run(out_dir=None):
    """Full routine: extract → accrue → reconcile → hibalista files → load into dashboard.db.
    Returns a summary dict (used by run_etl.py). Safe to call after load_all()."""
    out_dir = out_dir or os.path.join(ROOT, "scripts", "_out")
    os.makedirs(out_dir, exist_ok=True)

    rows = extract_rows()
    leftover_4 = [r for r in rows if r["division"] != "S" and re.match(r"^\d{4}$", r["base"])]
    order_years, reg_parse_fails = aggregate(rows)
    s_years = aggregate_s(rows)
    s_keys = s_keys_of(rows)
    quotes, quote_parse_fails, quote_collisions = load_quote_groups()

    # ---- per-MSZ rollup (for reconciliation + hibalista) ----
    by_msz = {}
    for o in order_years:
        m = by_msz.setdefault(o["key"], {"product_line": o["product_line"], "canonical_msz": o["canonical_msz"],
                                         "customer": o["customer"], "wn_year": o["wn_year"], "value_eur": 0.0,
                                         "years": set()})
        m["value_eur"] += o["value_eur"] or 0
        m["years"].add(o["register_year"])
        if not m["customer"]:
            m["customer"] = o["customer"]
    won_keys = {k for k, v in quotes.items() if v["status"] == "WON"}
    orphan = sorted(k for k in by_msz if k not in quotes)                      # rendelés, nincs quote
    status_mismatch = sorted(k for k in by_msz if k in quotes and quotes[k]["status"] != "WON")
    won_termekcsoport3 = [k for k in won_keys if k not in by_msz and k in s_keys]    # TG1→termékcsoport3
    won_missing = [k for k in won_keys if k not in by_msz and k not in s_keys]

    # ---- clean munkatábla (one row per MSZ × register year) ----
    clean_csv = os.path.join(out_dir, "work_orders_clean.csv")
    with open(clean_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["canonical_msz", "product_line", "register_year", "wn_year", "customer",
                    "value_eur", "k_eur", "p_eur", "n_parts", "has_quote", "quote_status"])
        for o in sorted(order_years, key=lambda o: (o["product_line"], o["register_year"], o["canonical_msz"])):
            q = quotes.get(o["key"])
            w.writerow([o["canonical_msz"], o["product_line"], o["register_year"], o["wn_year"], o["customer"],
                        o["value_eur"], o["k_eur"], o["p_eur"], o["n_parts"],
                        1 if q else 0, q["status"] if q else ""])

    # ---- hibalista (order-driven) -> CSV + XLSX ----
    qidx = quote_partner_index(DB)
    hiba_cols = ["kategória", "product_line", "MSZ", "ügyfél", "EUR", "javasolt_művelet"]
    hiba_rows = []
    for k in orphan:
        m = by_msz[k]
        if m["wn_year"] < 2023:
            cat, action = "· pre-2023 (lefedés előtti)", "—"
        else:
            cat, action = triage_orphan(m["customer"], qidx)
        hiba_rows.append([cat, m["product_line"], m["canonical_msz"], m["customer"],
                          round(m["value_eur"] or 0), action])
    for k in status_mismatch:
        m, q = by_msz[k], quotes[k]
        hiba_rows.append(["rendelés van, quote NEM WON", m["product_line"], m["canonical_msz"],
                          m["customer"], round(m["value_eur"] or 0),
                          f"ajánlat={q.get('quote_id', '')} státusz={q['status']} → frissítsd WON-ra"])
    for k in won_termekcsoport3:
        q = quotes[k]
        hiba_rows.append(["TG1→termékcsoport3(S) átsorolás", q["product_line"], q["work_number"], "",
                          round(q["value"] or 0), "a quote TG1-besorolása téves → termékcsoport3, ne számítson TG1-nek"])
    for k in won_missing:
        q = quotes[k]
        hiba_rows.append(["WON quote, rendelés hiányzik", q["product_line"], q["work_number"], "",
                          round(q["value"] or 0), "vedd fel a rendelést / ellenőrizd a MSZ-t"])
    for r in reg_parse_fails:
        hiba_rows.append(["regiszter MSZ-elírás", "?", r["raw_msz"], r["customer"],
                          round(r["k_eur"] or r["p_eur"] or 0), "javítsd a munkaszámot a forrásban"])
    for pl, wn, st in quote_parse_fails:
        hiba_rows.append(["quote MSZ-elírás", pl, str(wn), "", "",
                          f"status={st} → javítsd a munkaszámot a quote-ban"])
    for key, lst in quote_collisions:
        reg_cust = by_msz[key]["customer"] if key in by_msz else "?"
        for x in lst:  # minden érintett sor — döntsd el melyiké a MSZ, a többit javítsd
            hiba_rows.append(["MSZ-ütközés a quote-ban", x["product_line"], canon_msz(key), x["partner"],
                              round(x["value"] or 0),
                              f"ajánlat={x['quote_id']} ({x['registry']}) státusz={x['status']} | regiszter szerint: {reg_cust} — egy MSZ-en több ügyfél, javítsd a rosszat"])

    # gyanús elhatárolás: ugyanaz az MSZ, ~azonos érték ismétlődik több évben (lehet duplikáció
    # vagy valódi 50-50 elhatárolás) -> az összeg marad a SoT, de jelöljük emberi ellenőrzésre
    msz_years = defaultdict(list)
    for o in order_years:
        msz_years[o["key"]].append((o["register_year"], o["value_eur"] or 0))
    for key, yrs in sorted(msz_years.items()):
        vals = [v for _, v in yrs]
        if len(vals) > 1 and any(a and abs(a - b) <= 0.01 * max(a, b)
                                 for i, a in enumerate(vals) for b in vals[i + 1:]):
            m = by_msz[key]
            yr_str = " | ".join(f"{y}:{int(v):,}" for y, v in sorted(yrs))
            hiba_rows.append(["gyanús elhatárolás (azonos érték ismétlődik)", m["product_line"],
                              m["canonical_msz"], m["customer"], round(m["value_eur"] or 0),
                              f"évenként: {yr_str} — lehet duplikáció v. 50-50 elhatárolás; ellenőrizd (értékként az összeg számít)"])

    hiba_csv = os.path.join(out_dir, "work_orders_hibalista.csv")
    with open(hiba_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(hiba_cols)
        w.writerows(hiba_rows)
    hiba_xlsx = os.path.join(out_dir, "work_orders_hibalista.xlsx")
    write_xlsx(hiba_cols, hiba_rows, hiba_xlsx, widths=[30, 6, 9, 26, 11, 46])

    # ---- LOAD into dashboard.db ----
    src_files = {fy: os.path.getmtime(os.path.join(DATA, f"rendelesi_regiszter_{fy}.xlsx")) for fy in FILE_YEARS}
    import datetime as _dt
    load_to_db(order_years, s_years, quotes, DB, meta={
        "hibalista_count": len(hiba_rows),
        "hibalista_xlsx": hiba_xlsx,
        "source_latest_mtime": _dt.datetime.fromtimestamp(max(src_files.values())).isoformat(timespec="seconds"),
        "source_years": ",".join(str(y) for y in FILE_YEARS),
    })

    # ---- summary ----
    n_s = sum(1 for r in rows if r["division"] == "S")
    n_self = sum(1 for r in rows if r["division"] == "SELF")
    tg1_eur = sum(o["value_eur"] or 0 for o in order_years if o["product_line"] == "TG1")
    tg2_eur = sum(o["value_eur"] or 0 for o in order_years if o["product_line"] == "TG2")
    tg1_msz = len({k for k in by_msz if k[0] == "TG1"})
    tg2_msz = len({k for k in by_msz if k[0] == "TG2"})

    print("=" * 66)
    print(" RENDELÉSI REGISZTER — elhatárolás-alapú kivonat + egyeztetés")
    print("=" * 66)
    print(f"Kivett sorok: {len(rows)}  (E/TG2={len(rows) - n_s - n_self}, "
          f"S/termékcsoport3={n_s}, saját gyártás={n_self} — kizárva)")
    print(f"Konzisztencia (S után maradó 4-jegyű): {len(leftover_4)}  {'OK' if not leftover_4 else 'HIBA!'}")
    print(f"work_orders sorok (MSZ × nyilv. év): {len(order_years)}  |  egyedi MSZ: TG1={tg1_msz} TG2={tg2_msz}")
    print(f"EUR SoT (elhatárolva, K↘P): TG1={tg1_eur:,.0f}  TG2={tg2_eur:,.0f}  összesen={tg1_eur + tg2_eur:,.0f} EUR")
    print("-" * 66)
    print("EUR SoT nyilvántartási évenként:")
    by_year = defaultdict(lambda: defaultdict(float))
    for o in order_years:
        by_year[o["register_year"]][o["product_line"]] += o["value_eur"] or 0
    for o in s_years:
        by_year[o["register_year"]]["S"] += o["value_eur"] or 0
    for y in sorted(by_year):
        print(f"   {y}:  TG1={by_year[y]['TG1']:>12,.0f}   TG2={by_year[y]['TG2']:>11,.0f}   S(termékcsoport3)={by_year[y]['S']:>11,.0f}")
    print("-" * 66)
    print("Egyeztetés (MSZ-szinten):")
    print(f"  rendelés VAN quote-tal: {sum(1 for k in by_msz if k in quotes)}")
    print(f"  rendelés quote NÉLKÜL:  {len(orphan)}")
    print(f"  rendelés van, quote NEM WON: {len(status_mismatch)}  -> {[by_msz[k]['canonical_msz'] for k in status_mismatch]}")
    print(f"  TG1 quote → regiszter S (termékcsoport3): {len(won_termekcsoport3)}  -> {[quotes[k]['work_number'] for k in won_termekcsoport3]}")
    print(f"  WON quote valóban hiányzik: {len(won_missing)}  -> {[quotes[k]['work_number'] for k in won_missing]}")
    print(f"  MSZ-elírás: regiszter {len(reg_parse_fails)}, quote {len(quote_parse_fails)}")
    print(f"  MSZ-ütközés (egy MSZ, több ügyfél): {len(quote_collisions)}  -> {[canon_msz(k) for k, _ in quote_collisions]}")
    print("-" * 66)
    print(f"work_orders BETÖLTVE a dashboard.db-be (+ v_work_orders_eur, v_work_reconciliation)")
    print(f"Hibalista tételek: {len(hiba_rows)}")
    print(f"Kiírva:\n  {clean_csv}\n  {hiba_csv}\n  {hiba_xlsx}")
    return {"rows": len(order_years) + len(s_years), "tg1_eur": tg1_eur, "tg2_eur": tg2_eur,
            "s_eur": sum(o["value_eur"] or 0 for o in s_years), "hibalista": len(hiba_rows),
            "hibalista_xlsx": hiba_xlsx}


def main():
    import argparse
    ap = argparse.ArgumentParser(description="rendelesi_regiszter → work_orders (dashboard.db) + hibalista")
    ap.add_argument("--out", default=None, help="kimeneti mappa (alapértelmezés: scripts/_out)")
    args = ap.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
