"""
Export JSON (contract v2) — query dashboard.db and produce data/dashboard_data.json.

This is the data contract between the SQL layer and the single-page dashboard
(generate_dashboard.py). The HTML never touches the database; everything it shows
is in this file, so every number on screen can be traced here and to a view.

Structure
---------
{
  "_meta":   {as_of, through_md, years, default_year, pipeline_window_months, register{...}, sources},
  "quality": {...global data-quality figures...},
  "scopes": {
    "all" | "tg1" | "tg2": {
      "label",
      "years":     {"2023": YEAR_BLOCK, ...},      # funnel by RFQ year (bank-report definitions)
      "monthly":   [{month, rfq_n, quoted_n, kiadott_eur, won_n, won_eur}, ...],
      "pipeline":  {live, prep, stale, top_live[], top_stale[]},   # snapshot, 12-month live rule
      "realized":  {"2023": {"TG1": {...}, "TG2": {...}, "S": {...}}, ...},  # register, accrual
      "quarterly": [{label, year, q, sent_n, sent_eur, won_n, won_eur, lost_n, win_rate}, ...],
    }
  }
}

YEAR_BLOCK (all numbers by the `year` column = RFQ year, same definitions as the bank report):
  rfq_n, partners_n, noquote_n, quoted_n, kiadott_eur, won_n/eur, lost_n/eur, postponed_n/eur,
  open_n/eur (QUOTED+PREPARATION), quoted_open_n/eur, prep_n/eur, cnr_n/eur, win_rate, conversion_pct,
  dom: {magyar, kulfoldi, na: {partners_n, kiadott_eur, won_eur, lost_eur, postponed_eur, open_eur, cnr_eur}},
  ytd: {cur, prev, through_md}   # same calendar window (Jan 1 – as_of month/day) this year vs previous
  partners: {total, new, returning, returning_pct, new_magyar, new_kulfoldi}
  countries: {n, top: [{country, kiadott_eur, won_eur, n}]}
  reaction: {avg_days, median_days, within7_pct, n}
  loss: [{status, label, n, eur}]
  is_partial, days_elapsed, annualize_factor
"""
import json
import logging
import sqlite3
from datetime import datetime, date

from config import DB_PATH, DATA_DIR

log = logging.getLogger(__name__)

CONTRACT_VERSION = 2
PIPELINE_WINDOW_MONTHS = 12
MIN_YEAR = 2023

SOURCES = {
    "funnel":    "etl/export_json.py::_funnel() — quotes by RFQ year (bank-report definitions)",
    "monthly":   "etl/export_json.py::_monthly() — quotes by request month",
    "pipeline":  "sql/views/04_pipeline.sql (v_pipeline, is_live = 12 hónap)",
    "realized":  "scripts/extract_work_orders.py → work_orders, v_work_orders_eur (accrual by register year)",
    "quarterly": "etl/export_json.py::_quarterly() — by sent_date quarter",
    "quality":   "etl/export_json.py::_quality()",
}

STATUS_LABELS = {
    "LOST_COMPETITOR": "Versenytárs nyerte",
    "LOST_CUSTOMER": "Vevő nem rendelte meg",
    "POSTPONED": "Elhalasztva",
    "CLOSED_NO_RESPONSE": "Nem válaszolt (auto-lezárt)",
}

SCOPES = {"all": (None, "Összes termékvonal"),
          "tg1": ("TG1", "TG1 – termékcsoport1"),
          "tg2": ("TG2", "TG2 – termékcsoport2")}


# ── helpers ──────────────────────────────────────────────────────────────────

def _rows(conn, sql, params=()):
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _one(conn, sql, params=()):
    r = _rows(conn, sql, params)
    return r[0] if r else {}


def _pl(pl):
    return "" if pl is None else f"AND q.product_line = '{pl}'"


def _r(v, nd=0):
    if v is None:
        return 0
    return round(v, nd) if nd else int(round(v))


# ── funnel (RFQ year) ────────────────────────────────────────────────────────

FUNNEL_SQL = """
SELECT COUNT(*)                                   AS rfq_n,
       COUNT(DISTINCT q.partner_name_raw)         AS partners_n,
       SUM(q.status = 'NO_QUOTE')                 AS noquote_n,
       SUM(q.status NOT IN ('NO_QUOTE','NOT_RELEVANT')) AS quoted_n,
       SUM(CASE WHEN q.status <> 'NO_QUOTE' THEN q.total_value_eur END)            AS kiadott_eur,
       SUM(q.status = 'WON')                                                        AS won_n,
       SUM(CASE WHEN q.status = 'WON' THEN q.total_value_eur END)                   AS won_eur,
       SUM(q.status LIKE 'LOST%')                                                   AS lost_n,
       SUM(CASE WHEN q.status LIKE 'LOST%' THEN q.total_value_eur END)              AS lost_eur,
       SUM(q.status = 'POSTPONED')                                                  AS postponed_n,
       SUM(CASE WHEN q.status = 'POSTPONED' THEN q.total_value_eur END)             AS postponed_eur,
       SUM(q.status IN ('QUOTED','PREPARATION'))                                    AS open_n,
       SUM(CASE WHEN q.status IN ('QUOTED','PREPARATION') THEN q.total_value_eur END) AS open_eur,
       SUM(q.status = 'QUOTED')                                                     AS quoted_open_n,
       SUM(CASE WHEN q.status = 'QUOTED' THEN q.total_value_eur END)                AS quoted_open_eur,
       SUM(q.status = 'PREPARATION')                                                AS prep_n,
       SUM(CASE WHEN q.status = 'PREPARATION' THEN q.total_value_eur END)           AS prep_eur,
       SUM(q.status = 'CLOSED_NO_RESPONSE')                                         AS cnr_n,
       SUM(CASE WHEN q.status = 'CLOSED_NO_RESPONSE' THEN q.total_value_eur END)    AS cnr_eur,
       AVG(CASE WHEN q.status NOT IN ('NO_QUOTE','NOT_RELEVANT') THEN q.reaction_days END) AS avg_reaction
FROM quotes q
WHERE q.year = ? {pl} {extra}
"""


def _funnel(conn, pl, year, extra="", params=()):
    d = _one(conn, FUNNEL_SQL.format(pl=_pl(pl), extra=extra), (year,) + params)
    out = {k: (_r(v) if v is not None else 0) for k, v in d.items() if k != "avg_reaction"}
    decided = out["won_n"] + out["lost_n"]
    out["win_rate"] = round(out["won_n"] / decided * 100, 1) if decided else None
    out["conversion_pct"] = round(out["won_eur"] / out["kiadott_eur"] * 100, 1) if out["kiadott_eur"] else None
    out["avg_reaction"] = round(d["avg_reaction"], 1) if d.get("avg_reaction") is not None else None
    return out


def _year_block(conn, pl, year, as_of):
    through_md = as_of.strftime("%m-%d")
    blk = _funnel(conn, pl, year)
    blk["dom"] = {
        "magyar":   _funnel(conn, pl, year, "AND q.is_domestic = 1"),
        "kulfoldi": _funnel(conn, pl, year, "AND q.is_domestic = 0"),
        "na":       _funnel(conn, pl, year, "AND q.is_domestic IS NULL"),
    }
    ytd_extra = "AND q.request_date IS NOT NULL AND SUBSTR(q.request_date, 6, 5) <= ?"
    blk["ytd"] = {
        "cur":  _funnel(conn, pl, year, ytd_extra, (through_md,)),
        "prev": _funnel(conn, pl, year - 1, ytd_extra, (through_md,)),
        "through_md": through_md,
    }
    blk["partners"] = _partners(conn, pl, year)
    blk["countries"] = _countries(conn, pl, year)
    blk["reaction"] = _reaction(conn, pl, year)
    blk["loss"] = _loss(conn, pl, year)
    is_partial = (year == as_of.year)
    days = (as_of - date(year, 1, 1)).days + 1 if is_partial else 365
    blk["is_partial"] = is_partial
    blk["days_elapsed"] = days
    blk["annualize_factor"] = round(365 / days, 2) if is_partial else 1.0
    return blk


def _partners(conn, pl, year):
    """New vs returning partners on the scope. Base = every year loaded (2023+ since the
    2020–2022 files were removed from the load on 2026-10-12)."""
    pl_sql = _pl(pl)
    rows = _rows(conn, f"""
        WITH f AS (SELECT q.partner_id, MIN(q.year) AS fy FROM quotes q WHERE 1=1 {pl_sql} GROUP BY q.partner_id),
             y AS (SELECT DISTINCT q.partner_id, MAX(q.is_domestic) AS dom FROM quotes q WHERE q.year = ? {pl_sql} GROUP BY q.partner_id)
        SELECT (f.fy = ?) AS is_new, y.dom, COUNT(*) AS n
        FROM y JOIN f USING(partner_id) GROUP BY 1, 2
    """, (year, year))
    total = sum(r["n"] for r in rows)
    new = sum(r["n"] for r in rows if r["is_new"])
    base_year = (year == MIN_YEAR)   # first loaded year: every partner looks "new" — no base to compare
    return {
        "total": total, "new": None if base_year else new, "returning": None if base_year else total - new,
        "returning_pct": None if base_year or not total else round((total - new) / total * 100),
        "base_year": base_year,
        "new_magyar": None if base_year else sum(r["n"] for r in rows if r["is_new"] and r["dom"] == 1),
        "new_kulfoldi": None if base_year else sum(r["n"] for r in rows if r["is_new"] and r["dom"] == 0),
    }


def _countries(conn, pl, year):
    pl_sql = _pl(pl)
    n = _one(conn, f"""SELECT COUNT(DISTINCT CASE WHEN q.country = 'Amerikai Egyesült Államok' THEN 'Egyesült Államok' ELSE q.country END) AS n
                       FROM quotes q WHERE q.year = ? AND q.country IS NOT NULL AND q.country <> '' {pl_sql}""", (year,))["n"]
    top = _rows(conn, f"""
        SELECT CASE WHEN q.country = 'Amerikai Egyesült Államok' THEN 'Egyesült Államok' ELSE q.country END AS country,
               MAX(q.is_domestic) AS is_domestic,
               COUNT(*) AS n,
               SUM(CASE WHEN q.status <> 'NO_QUOTE' THEN q.total_value_eur END) AS kiadott_eur,
               SUM(CASE WHEN q.status = 'WON' THEN q.total_value_eur END) AS won_eur
        FROM quotes q WHERE q.year = ? AND q.country IS NOT NULL AND q.country <> '' {pl_sql}
        GROUP BY 1 ORDER BY kiadott_eur DESC LIMIT 8
    """, (year,))
    for t in top:
        t["kiadott_eur"] = _r(t["kiadott_eur"]); t["won_eur"] = _r(t["won_eur"])
    return {"n": n, "top": top}


def _reaction(conn, pl, year):
    vals = [r["d"] for r in _rows(conn, f"""SELECT q.reaction_days AS d FROM quotes q
        WHERE q.year = ? AND q.reaction_days IS NOT NULL AND q.reaction_days >= 0
          AND q.status NOT IN ('NO_QUOTE','NOT_RELEVANT') {_pl(pl)} ORDER BY 1""", (year,))]
    if not vals:
        return {"avg_days": None, "median_days": None, "within7_pct": None, "n": 0}
    m = len(vals) // 2
    median = vals[m] if len(vals) % 2 else (vals[m - 1] + vals[m]) / 2
    return {"avg_days": round(sum(vals) / len(vals), 1), "median_days": round(median, 1),
            "within7_pct": round(sum(1 for v in vals if v <= 7) / len(vals) * 100), "n": len(vals)}


def _loss(conn, pl, year):
    rows = _rows(conn, f"""SELECT q.status, COUNT(*) AS n, SUM(q.total_value_eur) AS eur FROM quotes q
        WHERE q.year = ? AND q.status IN ('LOST_COMPETITOR','LOST_CUSTOMER','POSTPONED','CLOSED_NO_RESPONSE') {_pl(pl)}
        GROUP BY q.status ORDER BY n DESC""", (year,))
    return [{"status": r["status"], "label": STATUS_LABELS.get(r["status"], r["status"]),
             "n": r["n"], "eur": _r(r["eur"])} for r in rows]


# ── monthly (request month) ──────────────────────────────────────────────────

def _monthly(conn, pl, as_of):
    rows = _rows(conn, f"""
        SELECT SUBSTR(q.request_date, 1, 7) AS month, COUNT(*) AS rfq_n,
               SUM(q.status NOT IN ('NO_QUOTE','NOT_RELEVANT')) AS quoted_n,
               SUM(CASE WHEN q.status <> 'NO_QUOTE' THEN q.total_value_eur END) AS kiadott_eur,
               SUM(q.status = 'WON') AS won_n,
               SUM(CASE WHEN q.status = 'WON' THEN q.total_value_eur END) AS won_eur
        FROM quotes q WHERE q.request_date IS NOT NULL AND q.year >= {MIN_YEAR} {_pl(pl)}
        GROUP BY 1 ORDER BY 1""")
    lookup = {r["month"]: r for r in rows}
    out = []
    y, m = MIN_YEAR, 1
    while (y, m) <= (as_of.year, as_of.month):
        key = f"{y}-{m:02d}"
        r = lookup.get(key, {})
        out.append({"month": key, "rfq_n": r.get("rfq_n", 0) or 0, "quoted_n": r.get("quoted_n", 0) or 0,
                    "kiadott_eur": _r(r.get("kiadott_eur")), "won_n": r.get("won_n", 0) or 0,
                    "won_eur": _r(r.get("won_eur"))})
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


# ── pipeline snapshot (v_pipeline) ───────────────────────────────────────────

def _pipeline(conn, pl):
    pl_sql = "" if pl is None else f"AND product_line = '{pl}'"
    agg = _one(conn, f"""
        SELECT SUM(is_live = 1 AND status = 'QUOTED') AS live_n,
               SUM(CASE WHEN is_live = 1 AND status = 'QUOTED' THEN total_value_eur END) AS live_eur,
               SUM(is_live = 1 AND status = 'PREPARATION') AS prep_n,
               SUM(CASE WHEN is_live = 1 AND status = 'PREPARATION' THEN total_value_eur END) AS prep_eur,
               SUM(is_live = 0) AS stale_n,
               SUM(CASE WHEN is_live = 0 THEN total_value_eur END) AS stale_eur,
               SUM(is_live = 1 AND status = 'QUOTED' AND age_days <= 90) AS live_90_n,
               SUM(CASE WHEN is_live = 1 AND status = 'QUOTED' AND age_days <= 90 THEN total_value_eur END) AS live_90_eur
        FROM v_pipeline WHERE 1=1 {pl_sql}""")
    cols = "quote_id, product_line, partner, country, is_domestic, subject, total_value_eur AS eur, request_date, age_days, status"
    top_live = _rows(conn, f"SELECT {cols} FROM v_pipeline WHERE is_live = 1 AND status = 'QUOTED' {pl_sql} ORDER BY total_value_eur DESC LIMIT 10")
    top_stale = _rows(conn, f"SELECT {cols} FROM v_pipeline WHERE is_live = 0 {pl_sql} ORDER BY total_value_eur DESC LIMIT 10")
    for t in top_live + top_stale:
        t["eur"] = _r(t["eur"])
    g = lambda k: _r(agg.get(k)) if agg.get(k) is not None else 0
    return {
        "live": {"n": g("live_n"), "eur": g("live_eur")},
        "live_90": {"n": g("live_90_n"), "eur": g("live_90_eur")},
        "prep": {"n": g("prep_n"), "eur": g("prep_eur")},
        "stale": {"n": g("stale_n"), "eur": g("stale_eur")},
        "top_live": top_live, "top_stale": top_stale,
    }


# ── realized (register) ──────────────────────────────────────────────────────

def _register_loaded(conn):
    return bool(conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='work_orders'").fetchone())


def _realized(conn):
    """Per register year × product line (TG1 / TG2 / S), accrual values from v_work_orders_eur."""
    if not _register_loaded(conn):
        return {}
    out = {}
    for r in _rows(conn, "SELECT * FROM v_work_orders_eur ORDER BY year, product_line"):
        out.setdefault(str(r["year"]), {})[r["product_line"]] = {
            "eur": _r(r["eur_sot"]), "n": r["distinct_msz"],
            "magyar": _r(r["eur_magyar"]), "kulfoldi": _r(r["eur_kulfoldi"]), "na": _r(r["eur_besorolatlan"]),
        }
    return out


def _register_meta(conn):
    if not _register_loaded(conn):
        return {"loaded": False}
    meta = {r["key"]: r["value"] for r in _rows(conn, "SELECT key, value FROM work_orders_meta")} \
        if conn.execute("SELECT name FROM sqlite_master WHERE name='work_orders_meta'").fetchone() else {}
    meta["loaded"] = True
    if meta.get("hibalista_xlsx"):
        import os
        try:
            meta["hibalista_xlsx"] = os.path.relpath(meta["hibalista_xlsx"], str(DATA_DIR.parent))
        except ValueError:
            pass
    try:
        meta["hibalista_count"] = int(meta.get("hibalista_count", 0))
        meta["customer_unresolved_rows"] = int(meta.get("customer_unresolved_rows", 0))
    except ValueError:
        pass
    return meta


# ── quarterly issuing performance (sent_date) ────────────────────────────────

def _quarterly(conn, pl):
    rows = _rows(conn, f"""
        SELECT CAST(SUBSTR(q.sent_date, 1, 4) AS INTEGER) AS year,
               (CAST(SUBSTR(q.sent_date, 6, 2) AS INTEGER) + 2) / 3 AS q,
               COUNT(*) AS sent_n, SUM(q.total_value_eur) AS sent_eur,
               SUM(q.status = 'WON') AS won_n, SUM(CASE WHEN q.status = 'WON' THEN q.total_value_eur END) AS won_eur,
               SUM(q.status LIKE 'LOST%') AS lost_n
        FROM quotes q
        WHERE q.sent_date IS NOT NULL AND CAST(SUBSTR(q.sent_date, 1, 4) AS INTEGER) >= {MIN_YEAR}
          AND q.status NOT IN ('PREPARATION','ORDER_LINE','NO_QUOTE','NOT_RELEVANT') {_pl(pl)}
        GROUP BY 1, 2 ORDER BY 1, 2""")
    out = []
    for r in rows:
        decided = (r["won_n"] or 0) + (r["lost_n"] or 0)
        out.append({"label": f"{r['year']} Q{int(r['q'])}", "year": r["year"], "q": int(r["q"]),
                    "sent_n": r["sent_n"], "sent_eur": _r(r["sent_eur"]), "won_n": r["won_n"] or 0,
                    "won_eur": _r(r["won_eur"]), "lost_n": r["lost_n"] or 0,
                    "win_rate": round((r["won_n"] or 0) / decided * 100, 1) if decided else None})
    return out


# ── global data quality ──────────────────────────────────────────────────────

def _quality(conn, as_of):
    q = {}
    for pl in ("TG1", "TG2"):
        d = _one(conn, f"""SELECT COUNT(*) AS n, SUM(q.country IS NOT NULL AND q.country <> '') AS with_country,
                            SUM(q.request_date IS NULL) AS no_date, SUM(q.status IS NULL) AS no_status,
                            SUM(q.total_value_eur IS NULL AND q.status NOT IN ('NO_QUOTE','NOT_RELEVANT','PREPARATION')) AS no_value
                            FROM quotes q WHERE q.year >= {MIN_YEAR} AND q.product_line = '{pl}'""")
        q[pl.lower()] = {"n": d["n"], "country_cov_pct": round(d["with_country"] / d["n"] * 100, 1) if d["n"] else None,
                         "no_date": d["no_date"], "no_status": d["no_status"], "no_value": d["no_value"]}
    st = _one(conn, "SELECT SUM(is_live = 0) AS n, SUM(CASE WHEN is_live = 0 THEN total_value_eur END) AS eur FROM v_pipeline")
    q["stale_open"] = {"n": st["n"] or 0, "eur": _r(st["eur"])}
    q["partners_total"] = _one(conn, "SELECT COUNT(*) AS n FROM partners")["n"]
    q["partners_no_country"] = _one(conn, "SELECT COUNT(*) AS n FROM partners WHERE country IS NULL OR country = ''")["n"]
    q["register"] = _register_meta(conn)
    if q["register"].get("loaded"):
        cov = _one(conn, """SELECT SUM(value_eur) AS tot, SUM(CASE WHEN is_domestic IS NOT NULL THEN value_eur END) AS res
                            FROM work_orders WHERE product_line IN ('TG1','TG2')""")
        q["register"]["country_cov_pct"] = round((cov["res"] or 0) / cov["tot"] * 100, 1) if cov["tot"] else None
    return q


# ── main ─────────────────────────────────────────────────────────────────────

def export():
    conn = sqlite3.connect(str(DB_PATH))
    as_of_s = conn.execute("SELECT MAX(request_date) FROM quotes").fetchone()[0]
    as_of = datetime.strptime(as_of_s[:10], "%Y-%m-%d").date()
    years = [r[0] for r in conn.execute("SELECT DISTINCT year FROM quotes WHERE year >= ? ORDER BY year", (MIN_YEAR,))]
    log.info("as_of=%s years=%s", as_of, years)

    realized = _realized(conn)
    scopes = {}
    for key, (pl, label) in SCOPES.items():
        scopes[key] = {
            "label": label,
            "years": {str(y): _year_block(conn, pl, y, as_of) for y in years},
            "monthly": _monthly(conn, pl, as_of),
            "pipeline": _pipeline(conn, pl),
            "realized": realized,
            "quarterly": _quarterly(conn, pl),
        }

    data = {
        "_meta": {
            "contract": CONTRACT_VERSION,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "as_of": as_of.isoformat(),
            "through_md": as_of.strftime("%m-%d"),
            "latest_month": as_of.strftime("%Y-%m"),
            "years": years,
            "default_year": str(years[-1]) if years else None,
            "pipeline_window_months": PIPELINE_WINDOW_MONTHS,
            "register": _register_meta(conn),
            "sources": SOURCES,
        },
        "quality": _quality(conn, as_of),
        "scopes": scopes,
    }
    conn.close()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / "dashboard_data.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("JSON exported to %s (%d KB)", out_path, out_path.stat().st_size // 1024)
    return out_path


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
    export()
