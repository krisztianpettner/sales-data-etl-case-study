"""
Status dictionary management routes for the admin interface.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "etl"))
from config import STATUS_MAP

from flask import Blueprint, render_template, request, redirect, url_for, flash
from db.helpers import query, execute

bp = Blueprint("status_dict", __name__, url_prefix="/status")

FLAG_MAP = {
    "PREPARATION":        (1, 0, 0),
    "QUOTED":             (1, 0, 0),
    "WON":                (0, 1, 0),
    "LOST_COMPETITOR":    (0, 0, 1),
    "LOST_CUSTOMER":      (0, 0, 1),
    "POSTPONED":          (0, 0, 0),
    "CLOSED_NO_RESPONSE": (0, 0, 0),
    "NO_QUOTE":           (0, 0, 0),
    "NOT_RELEVANT":       (0, 0, 0),
    "ORDER_LINE":         (0, 0, 0),
}

NORMALIZED_VALUES = list(FLAG_MAP.keys())


@bp.route("/")
def list_status():
    custom_entries = query(
        "SELECT * FROM status_dictionary ORDER BY raw_status"
    )

    # Build built-in entries from STATUS_MAP for display
    builtin_entries = []
    for raw, (norm, is_open, is_won, is_lost) in STATUS_MAP.items():
        builtin_entries.append({
            "raw_status": raw,
            "normalized": norm,
            "is_open": is_open,
            "is_won": is_won,
            "is_lost": is_lost,
        })
    builtin_entries.sort(key=lambda x: x["raw_status"])

    return render_template(
        "status/list.html",
        custom_entries=custom_entries,
        builtin_entries=builtin_entries,
        normalized_values=NORMALIZED_VALUES,
    )


@bp.route("/add", methods=["POST"])
def add_status():
    raw_status = request.form.get("raw_status", "").strip()
    normalized = request.form.get("normalized", "").strip()

    if not raw_status or not normalized:
        flash("A nyers státusz és a normalizált érték megadása kötelező.", "danger")
        return redirect(url_for("status_dict.list_status"))

    if normalized not in FLAG_MAP:
        flash("Érvénytelen normalizált érték.", "danger")
        return redirect(url_for("status_dict.list_status"))

    is_open, is_won, is_lost = FLAG_MAP[normalized]

    try:
        execute(
            """INSERT INTO status_dictionary (raw_status, normalized, is_open, is_won, is_lost)
               VALUES (?, ?, ?, ?, ?)""",
            (raw_status, normalized, is_open, is_won, is_lost),
        )
        flash("Státusz hozzáadva.", "success")
    except Exception:
        flash("Ez a nyers státusz már szerepel a szótárban.", "warning")

    return redirect(url_for("status_dict.list_status"))


@bp.route("/<int:entry_id>/edit", methods=["POST"])
def edit_status(entry_id):
    normalized = request.form.get("normalized", "").strip()
    raw_status = request.form.get("raw_status", "").strip()

    if not normalized or normalized not in FLAG_MAP:
        flash("Érvénytelen normalizált érték.", "danger")
        return redirect(url_for("status_dict.list_status"))

    is_open, is_won, is_lost = FLAG_MAP[normalized]

    execute(
        """UPDATE status_dictionary
           SET raw_status=?, normalized=?, is_open=?, is_won=?, is_lost=?
           WHERE id=?""",
        (raw_status, normalized, is_open, is_won, is_lost, entry_id),
    )
    flash("Státusz frissítve.", "success")
    return redirect(url_for("status_dict.list_status"))


@bp.route("/<int:entry_id>/delete", methods=["POST"])
def delete_status(entry_id):
    execute("DELETE FROM status_dictionary WHERE id = ?", (entry_id,))
    flash("Státusz törölve.", "success")
    return redirect(url_for("status_dict.list_status"))
