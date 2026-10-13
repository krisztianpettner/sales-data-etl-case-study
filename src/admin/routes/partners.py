"""
Partner management routes for the admin interface.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "etl"))
from transform import normalize_name

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from db.helpers import query, execute, get_db, next_partner_id

bp = Blueprint("partners", __name__, url_prefix="/partners")

PAGE_SIZE = 50


@bp.route("/")
def list_partners():
    q = request.args.get("q", "").strip()
    country = request.args.get("country", "").strip()
    ptype = request.args.get("type", "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1

    offset = (page - 1) * PAGE_SIZE

    sql = """
        SELECT pm.partner_id, pm.display_name, pm.country, pm.partner_type,
               pm.industry, pm.name_normalized,
               COUNT(pa.id) AS alias_count
        FROM partner_master pm
        LEFT JOIN partner_aliases pa ON pa.partner_id = pm.partner_id
        WHERE 1=1
    """
    params = []

    if q:
        sql += " AND (pm.display_name LIKE ? OR pm.name_normalized LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if country:
        sql += " AND pm.country = ?"
        params.append(country)
    if ptype:
        sql += " AND pm.partner_type = ?"
        params.append(ptype)

    sql += " GROUP BY pm.partner_id ORDER BY pm.display_name"

    count_sql = f"SELECT COUNT(*) AS cnt FROM ({sql})"
    total_row = query(count_sql, params, one=True)
    total = total_row["cnt"] if total_row else 0

    sql += " LIMIT ? OFFSET ?"
    params += [PAGE_SIZE, offset]

    partners = query(sql, params)

    countries = [
        r["country"]
        for r in query(
            "SELECT DISTINCT country FROM partner_master WHERE country IS NOT NULL ORDER BY country"
        )
    ]
    types = [
        r["partner_type"]
        for r in query(
            "SELECT DISTINCT partner_type FROM partner_master WHERE partner_type IS NOT NULL ORDER BY partner_type"
        )
    ]

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    return render_template(
        "partners/list.html",
        partners=partners,
        q=q,
        country=country,
        ptype=ptype,
        countries=countries,
        types=types,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@bp.route("/new", methods=["GET"])
def new_partner():
    return render_template("partners/edit.html", partner=None, aliases=[])


@bp.route("/new", methods=["POST"])
def create_partner():
    display_name = request.form.get("display_name", "").strip()
    if not display_name:
        flash("A partner neve kötelező.", "danger")
        return render_template("partners/edit.html", partner=None, aliases=[])

    partner_id = next_partner_id()
    norm = normalize_name(display_name)

    execute(
        """INSERT INTO partner_master
           (partner_id, display_name, name_normalized, official_name, country,
            tax_id_hu, vat_eu, partner_type, industry, teaor_code, website, notes, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            partner_id,
            display_name,
            norm,
            request.form.get("official_name", "").strip() or None,
            request.form.get("country", "").strip() or None,
            request.form.get("tax_id_hu", "").strip() or None,
            request.form.get("vat_eu", "").strip() or None,
            request.form.get("partner_type", "").strip() or None,
            request.form.get("industry", "").strip() or None,
            request.form.get("teaor_code", "").strip() or None,
            request.form.get("website", "").strip() or None,
            request.form.get("notes", "").strip() or None,
        ),
    )
    flash(f"Partner létrehozva: {partner_id}", "success")
    return redirect(url_for("partners.edit_partner", partner_id=partner_id))


@bp.route("/merge", methods=["GET"])
def merge_partners():
    return render_template("partners/merge.html")


@bp.route("/merge", methods=["POST"])
def do_merge():
    kept_id = request.form.get("kept_id", "").strip()
    merged_id = request.form.get("merged_id", "").strip()

    if not kept_id or not merged_id:
        flash("Mindkét partner megadása kötelező.", "danger")
        return redirect(url_for("partners.merge_partners"))
    if kept_id == merged_id:
        flash("Nem lehet ugyanazt a partnert összevonni önmagával.", "danger")
        return redirect(url_for("partners.merge_partners"))

    kept = query("SELECT * FROM partner_master WHERE partner_id = ?", (kept_id,), one=True)
    merged = query("SELECT * FROM partner_master WHERE partner_id = ?", (merged_id,), one=True)

    if not kept or not merged:
        flash("Érvénytelen partner azonosító.", "danger")
        return redirect(url_for("partners.merge_partners"))

    db = get_db()

    # Move aliases from merged to kept (avoid duplicates)
    db.execute(
        """INSERT OR IGNORE INTO partner_aliases (partner_id, alias_name, name_normalized, source)
           SELECT ?, alias_name, name_normalized, source
           FROM partner_aliases WHERE partner_id = ?""",
        (kept_id, merged_id),
    )

    # Also add the merged partner's display_name as an alias
    merged_norm = normalize_name(merged["display_name"])
    db.execute(
        """INSERT OR IGNORE INTO partner_aliases (partner_id, alias_name, name_normalized, source)
           VALUES (?, ?, ?, 'manual')""",
        (kept_id, merged["display_name"], merged_norm),
    )

    # Record the merge
    db.execute(
        """INSERT INTO partner_merges (kept_id, merged_id, merged_name)
           VALUES (?, ?, ?)""",
        (kept_id, merged_id, merged["display_name"]),
    )

    # Delete merged partner
    db.execute("DELETE FROM partner_aliases WHERE partner_id = ?", (merged_id,))
    db.execute("DELETE FROM partner_master WHERE partner_id = ?", (merged_id,))
    db.commit()

    flash(
        f"Összevonva: {merged['display_name']} ({merged_id}) → {kept['display_name']} ({kept_id})",
        "success",
    )
    return redirect(url_for("partners.edit_partner", partner_id=kept_id))


@bp.route("/<partner_id>", methods=["GET"])
def edit_partner(partner_id):
    partner = query(
        "SELECT * FROM partner_master WHERE partner_id = ?", (partner_id,), one=True
    )
    if not partner:
        flash("Partner nem található.", "danger")
        return redirect(url_for("partners.list_partners"))

    aliases = query(
        "SELECT * FROM partner_aliases WHERE partner_id = ? ORDER BY alias_name",
        (partner_id,),
    )
    return render_template("partners/edit.html", partner=partner, aliases=aliases)


@bp.route("/<partner_id>", methods=["POST"])
def update_partner(partner_id):
    partner = query(
        "SELECT * FROM partner_master WHERE partner_id = ?", (partner_id,), one=True
    )
    if not partner:
        flash("Partner nem található.", "danger")
        return redirect(url_for("partners.list_partners"))

    display_name = request.form.get("display_name", "").strip()
    if not display_name:
        flash("A partner neve kötelező.", "danger")
        aliases = query(
            "SELECT * FROM partner_aliases WHERE partner_id = ? ORDER BY alias_name",
            (partner_id,),
        )
        return render_template("partners/edit.html", partner=partner, aliases=aliases)

    norm = normalize_name(display_name)

    execute(
        """UPDATE partner_master SET
           display_name=?, name_normalized=?, official_name=?, country=?,
           tax_id_hu=?, vat_eu=?, partner_type=?, industry=?, teaor_code=?,
           website=?, notes=?, updated_at=datetime('now')
           WHERE partner_id=?""",
        (
            display_name,
            norm,
            request.form.get("official_name", "").strip() or None,
            request.form.get("country", "").strip() or None,
            request.form.get("tax_id_hu", "").strip() or None,
            request.form.get("vat_eu", "").strip() or None,
            request.form.get("partner_type", "").strip() or None,
            request.form.get("industry", "").strip() or None,
            request.form.get("teaor_code", "").strip() or None,
            request.form.get("website", "").strip() or None,
            request.form.get("notes", "").strip() or None,
            partner_id,
        ),
    )
    flash("Partner mentve.", "success")
    return redirect(url_for("partners.edit_partner", partner_id=partner_id))


@bp.route("/<partner_id>/alias", methods=["POST"])
def add_alias(partner_id):
    alias_name = request.form.get("alias_name", "").strip()
    if not alias_name:
        flash("Az alias neve kötelező.", "danger")
        return redirect(url_for("partners.edit_partner", partner_id=partner_id))

    norm = normalize_name(alias_name)
    try:
        execute(
            """INSERT INTO partner_aliases (partner_id, alias_name, name_normalized, source)
               VALUES (?, ?, ?, 'manual')""",
            (partner_id, alias_name, norm),
        )
        flash("Alias hozzáadva.", "success")
    except Exception:
        flash("Ez az alias már létezik.", "warning")

    return redirect(url_for("partners.edit_partner", partner_id=partner_id))


@bp.route("/<partner_id>/alias/<int:alias_id>/delete", methods=["POST"])
def delete_alias(partner_id, alias_id):
    execute(
        "DELETE FROM partner_aliases WHERE id = ? AND partner_id = ?",
        (alias_id, partner_id),
    )
    flash("Alias törölve.", "success")
    return redirect(url_for("partners.edit_partner", partner_id=partner_id))


@bp.route("/search")
def api_search():
    """Partner search API — used by import wizard and merge UI."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    rows = query(
        """SELECT partner_id, display_name, country, partner_type
           FROM partner_master
           WHERE display_name LIKE ? OR name_normalized LIKE ?
           ORDER BY display_name
           LIMIT 20""",
        (f"%{q}%", f"%{q}%"),
    )
    return jsonify([dict(r) for r in rows])
