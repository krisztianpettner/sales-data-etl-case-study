"""
Import wizard — 5-step guided import process.
Steps: 1. Upload  2. Partners  3. Statuses  4. Issues  5. Confirm
"""
import json
import os
import re
import sys
import uuid
from pathlib import Path

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, jsonify)

# ETL imports
_ETL_DIR = Path(__file__).resolve().parent.parent.parent / "etl"
if str(_ETL_DIR) not in sys.path:
    sys.path.insert(0, str(_ETL_DIR))

from db.helpers import get_db, query, execute, next_partner_id
import etl_bridge

bp = Blueprint("import_wizard", __name__, url_prefix="/import")

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"


def _detect_file_key(filename):
    """Auto-detect file type and year from filename.
    Returns file_key like 'TG1_2025' or 'TG2_2026', or None if unrecognized.
    """
    name = filename.lower()
    year_match = re.search(r'(20\d{2})', name)
    if not year_match:
        return None
    year = year_match.group(1)
    if 'tg2' in name:
        return f"TG2_{year}"
    if 'tg1' in name:
        return f"TG1_{year}"
    return None

WIZARD_STEPS = [
    {"num": 1, "label": "Fájlok",      "slug": "upload"},
    {"num": 2, "label": "Partnerek",    "slug": "partners"},
    {"num": 3, "label": "Státuszok",    "slug": "statuses"},
    {"num": 4, "label": "Hiánylista",   "slug": "issues"},
    {"num": 5, "label": "Jóváhagyás",  "slug": "confirm"},
]


def _get_session(session_id):
    """Load import session from admin.db."""
    return query(
        "SELECT * FROM import_sessions WHERE session_id = ?",
        (session_id,), one=True
    )


def _step_context(current_step, session_id=None):
    """Build context for wizard progress bar."""
    return {
        "wizard_steps": WIZARD_STEPS,
        "current_step": current_step,
        "session_id": session_id,
    }


# ═══════════════════════════════════════════════════════════════════════
#  Step 1: File Upload
# ═══════════════════════════════════════════════════════════════════════

@bp.route("/upload", methods=["GET"])
def upload():
    # Build per-file-key last import info (latest date + row count)
    history = query(
        """SELECT files_json, extract_summary, completed_at
           FROM import_sessions
           WHERE status = 'done'
           ORDER BY completed_at ASC""",
    )
    file_imports = {}  # key → {date, rows}
    for h in history:
        files = json.loads(h["files_json"]) if h["files_json"] else {}
        summary = json.loads(h["extract_summary"]) if h["extract_summary"] else {}
        for key in files:
            rows = summary.get(key, {}).get("rows", "?")
            file_imports[key] = {
                "date": (h["completed_at"] or "")[:16],
                "rows": rows,
            }

    return render_template(
        "import/upload.html",
        file_imports=file_imports,
        **_step_context(1),
    )


@bp.route("/upload", methods=["POST"])
def upload_post():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Create session
    sid = str(uuid.uuid4())
    file_paths = {}
    saved_count = 0
    unrecognized = []

    files = request.files.getlist("files")
    for f in files:
        if not f or not f.filename:
            continue
        key = _detect_file_key(f.filename)
        if not key:
            unrecognized.append(f.filename)
            continue
        dest = UPLOAD_DIR / f"{sid}_{key}_{f.filename}"
        f.save(str(dest))
        file_paths[key] = str(dest)
        saved_count += 1

    if unrecognized:
        flash(f"Nem felismert fájl(ok): {', '.join(unrecognized)}", "warning")

    if saved_count == 0:
        flash("Legalább egy felismerhető xlsx fájlt töltsön fel!", "error")
        return redirect(url_for("import_wizard.upload"))

    # Save session
    execute(
        """INSERT INTO import_sessions (session_id, status, files_json)
           VALUES (?, 'uploading', ?)""",
        (sid, json.dumps(file_paths))
    )

    # Run extract
    try:
        path_objs = {k: Path(v) for k, v in file_paths.items()}
        raw_data, summary = etl_bridge.run_extract(path_objs)
    except Exception as e:
        flash(f"Hiba az extract során: {e}", "error")
        execute("UPDATE import_sessions SET status='aborted' WHERE session_id=?", (sid,))
        return redirect(url_for("import_wizard.upload"))

    # Save extract summary
    execute(
        "UPDATE import_sessions SET extract_summary=? WHERE session_id=?",
        (json.dumps(summary, ensure_ascii=False), sid)
    )

    # Run staging transform (partner matching + status check)
    try:
        partner_staging, status_staging = etl_bridge.run_staging_transform(raw_data)
    except Exception as e:
        flash(f"Hiba a staging transform során: {e}", "error")
        execute("UPDATE import_sessions SET status='aborted' WHERE session_id=?", (sid,))
        return redirect(url_for("import_wizard.upload"))

    # Save to staging tables
    db = get_db()
    for p in partner_staging:
        db.execute(
            """INSERT INTO staging_partners
               (session_id, raw_name, name_normalized, match_score,
                matched_pm_id, zone, source_file, occurrence_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (sid, p["raw_name"], p["name_normalized"], p["match_score"],
             p.get("matched_pm_id"), p["zone"], p.get("source_file", ""),
             p.get("occurrence_count", 1))
        )

    # Pre-compute similarity between red entries (once, O(n²))
    from difflib import SequenceMatcher
    red_entries = [p for p in partner_staging if p["zone"] == "red"]
    red_norms = [(p["raw_name"], p["name_normalized"] or "") for p in red_entries]
    for i, (raw_i, norm_i) in enumerate(red_norms):
        best_score = 0.0
        best_match = ""
        if norm_i and len(norm_i) >= 3:
            for j, (raw_j, norm_j) in enumerate(red_norms):
                if i == j or not norm_j or len(norm_j) < 3:
                    continue
                score = SequenceMatcher(None, norm_i, norm_j).ratio()
                if score > best_score:
                    best_score = score
                    best_match = raw_j
        db.execute(
            """UPDATE staging_partners SET similarity=?, similar_to=?
               WHERE session_id=? AND raw_name=? AND zone='red'""",
            (best_score, best_match if best_score >= 0.6 else "", sid, raw_i)
        )

    unknown_statuses = [s for s in status_staging if not s.get("known")]
    for s in unknown_statuses:
        db.execute(
            """INSERT INTO staging_statuses
               (session_id, raw_status, quote_count)
               VALUES (?, ?, ?)""",
            (sid, s["raw_status"], s.get("quote_count", 0))
        )
    db.commit()

    # Update session status
    execute("UPDATE import_sessions SET status='partners' WHERE session_id=?", (sid,))

    flash(f"Extract kész: {summary}", "success")
    return redirect(url_for("import_wizard.partners", session_id=sid))


# ═══════════════════════════════════════════════════════════════════════
#  Step 2: Partner Matching
# ═══════════════════════════════════════════════════════════════════════

@bp.route("/partners/<session_id>", methods=["GET"])
def partners(session_id):
    sess = _get_session(session_id)
    if not sess:
        flash("Ismeretlen session!", "error")
        return redirect(url_for("import_wizard.upload"))

    staging = query(
        """SELECT * FROM staging_partners
           WHERE session_id = ?
           ORDER BY zone, match_score DESC""",
        (session_id,)
    )

    green = [r for r in staging if r["zone"] == "green"]
    yellow = [r for r in staging if r["zone"] == "yellow"]
    red = [r for r in staging if r["zone"] == "red"]

    pending_yellow = len([r for r in yellow if not r["decision"]])
    pending_red = len([r for r in red if not r["decision"]])

    return render_template(
        "import/partners.html",
        session=sess,
        green=green,
        yellow=yellow,
        red=red,
        pending_yellow=pending_yellow,
        pending_red=pending_red,
        all_resolved=(pending_yellow == 0 and pending_red == 0),
        **_step_context(2, session_id),
    )


@bp.route("/partners/<session_id>", methods=["POST"])
def partners_post(session_id):
    db = get_db()
    action = request.form.get("action", "save")

    if action == "reject":
        # Move a green entry to yellow
        staging_id = request.form.get("staging_id")
        db.execute(
            "UPDATE staging_partners SET zone='yellow', decision=NULL WHERE id=?",
            (staging_id,)
        )
        db.commit()
        return redirect(url_for("import_wizard.partners", session_id=session_id))

    if action == "bulk_new_red":
        # Create all unresolved red entries as new partners
        pending = db.execute(
            """SELECT id, raw_name, name_normalized FROM staging_partners
               WHERE session_id=? AND zone='red' AND decision IS NULL""",
            (session_id,)
        ).fetchall()
        for row in pending:
            new_pm = next_partner_id()
            display = row["raw_name"]
            norm = row["name_normalized"]
            db.execute(
                """INSERT INTO partner_master (partner_id, display_name, name_normalized)
                   VALUES (?, ?, ?)""",
                (new_pm, display, norm)
            )
            db.execute(
                """INSERT INTO partner_aliases (partner_id, alias_name, name_normalized, source)
                   VALUES (?, ?, ?, 'import')""",
                (new_pm, display, norm)
            )
            db.execute(
                """UPDATE staging_partners
                   SET decision='new', new_pm_id=?, resolved_at=datetime('now')
                   WHERE id=?""",
                (new_pm, row["id"])
            )
        db.commit()
        flash(f"{len(pending)} új partner létrehozva.", "success")
        return redirect(url_for("import_wizard.partners", session_id=session_id))

    if action == "save":
        # Process partner decisions from form
        for key, value in request.form.items():
            if key.startswith("decision_"):
                staging_id = key.replace("decision_", "")
                decision = value
                pm_id = request.form.get(f"pm_id_{staging_id}", "")
                new_name = request.form.get(f"new_name_{staging_id}", "")

                if decision == "accept":
                    db.execute(
                        """UPDATE staging_partners
                           SET decision='accept', resolved_at=datetime('now')
                           WHERE id=?""",
                        (staging_id,)
                    )
                elif decision == "reassign":
                    # Save raw_name as alias for the target partner
                    raw = db.execute(
                        "SELECT raw_name, name_normalized FROM staging_partners WHERE id=?",
                        (staging_id,)
                    ).fetchone()
                    if raw and pm_id:
                        db.execute(
                            """INSERT OR IGNORE INTO partner_aliases (partner_id, alias_name, name_normalized, source)
                               VALUES (?, ?, ?, 'import')""",
                            (pm_id, raw["raw_name"], raw["name_normalized"])
                        )
                    db.execute(
                        """UPDATE staging_partners
                           SET decision='reassign', matched_pm_id=?, resolved_at=datetime('now')
                           WHERE id=?""",
                        (pm_id, staging_id)
                    )
                elif decision == "new":
                    # Create new partner in admin.db
                    new_pm = next_partner_id()
                    raw = db.execute(
                        "SELECT raw_name, name_normalized FROM staging_partners WHERE id=?",
                        (staging_id,)
                    ).fetchone()
                    display = new_name.strip() if new_name and new_name.strip() else raw["raw_name"]
                    from transform import normalize_name
                    display_norm = normalize_name(display)
                    db.execute(
                        """INSERT INTO partner_master (partner_id, display_name, name_normalized)
                           VALUES (?, ?, ?)""",
                        (new_pm, display, display_norm)
                    )
                    # Display name as alias
                    db.execute(
                        """INSERT OR IGNORE INTO partner_aliases (partner_id, alias_name, name_normalized, source)
                           VALUES (?, ?, ?, 'import')""",
                        (new_pm, display, display_norm)
                    )
                    # Raw name as alias too (if different)
                    if raw["raw_name"].strip().lower() != display.strip().lower():
                        db.execute(
                            """INSERT OR IGNORE INTO partner_aliases (partner_id, alias_name, name_normalized, source)
                               VALUES (?, ?, ?, 'import')""",
                            (new_pm, raw["raw_name"], raw["name_normalized"])
                        )
                    db.execute(
                        """UPDATE staging_partners
                           SET decision='new', new_pm_id=?, resolved_at=datetime('now')
                           WHERE id=?""",
                        (new_pm, staging_id)
                    )
        db.commit()

    # Auto-accept green entries that haven't been decided yet
    db.execute(
        """UPDATE staging_partners
           SET decision='accept', resolved_at=datetime('now')
           WHERE session_id=? AND zone='green' AND decision IS NULL""",
        (session_id,)
    )
    db.commit()

    # Check if all resolved
    pending = query(
        """SELECT COUNT(*) as cnt FROM staging_partners
           WHERE session_id=? AND decision IS NULL""",
        (session_id,), one=True
    )

    if action == "next" or (pending and pending["cnt"] == 0):
        # Auto-accept remaining greens and move to next step
        db.execute(
            """UPDATE staging_partners
               SET decision='accept', resolved_at=datetime('now')
               WHERE session_id=? AND zone='green' AND decision IS NULL""",
            (session_id,)
        )
        db.commit()
        execute(
            "UPDATE import_sessions SET status='statuses' WHERE session_id=?",
            (session_id,)
        )
        return redirect(url_for("import_wizard.statuses", session_id=session_id))

    return redirect(url_for("import_wizard.partners", session_id=session_id))


# ═══════════════════════════════════════════════════════════════════════
#  AJAX: Save single partner decision
# ═══════════════════════════════════════════════════════════════════════

@bp.route("/partners/save_one", methods=["POST"])
def save_one_partner():
    """Save a single partner decision via AJAX."""
    from flask import jsonify
    from transform import normalize_name

    data = request.get_json()
    staging_id = data.get("staging_id")
    decision = data.get("decision")
    pm_id = data.get("pm_id", "")
    new_name = data.get("new_name", "")

    if not staging_id or not decision:
        return jsonify({"ok": False, "error": "Hiányzó adat"}), 400

    db = get_db()
    raw = db.execute(
        "SELECT raw_name, name_normalized, session_id FROM staging_partners WHERE id=?",
        (staging_id,)
    ).fetchone()
    if not raw:
        return jsonify({"ok": False, "error": "Nem található"}), 404

    result_pm_id = ""

    if decision == "accept":
        db.execute(
            """UPDATE staging_partners
               SET decision='accept', resolved_at=datetime('now')
               WHERE id=?""",
            (staging_id,)
        )

    elif decision == "reassign":
        if not pm_id:
            return jsonify({"ok": False, "error": "PM-ID szükséges"}), 400
        db.execute(
            """INSERT OR IGNORE INTO partner_aliases (partner_id, alias_name, name_normalized, source)
               VALUES (?, ?, ?, 'import')""",
            (pm_id, raw["raw_name"], raw["name_normalized"])
        )
        db.execute(
            """UPDATE staging_partners
               SET decision='reassign', matched_pm_id=?, resolved_at=datetime('now')
               WHERE id=?""",
            (pm_id, staging_id)
        )
        result_pm_id = pm_id

    elif decision == "new":
        new_pm = next_partner_id()
        display = new_name.strip() if new_name and new_name.strip() else raw["raw_name"]
        display_norm = normalize_name(display)
        db.execute(
            """INSERT INTO partner_master (partner_id, display_name, name_normalized)
               VALUES (?, ?, ?)""",
            (new_pm, display, display_norm)
        )
        db.execute(
            """INSERT OR IGNORE INTO partner_aliases (partner_id, alias_name, name_normalized, source)
               VALUES (?, ?, ?, 'import')""",
            (new_pm, display, display_norm)
        )
        if raw["raw_name"].strip().lower() != display.strip().lower():
            db.execute(
                """INSERT OR IGNORE INTO partner_aliases (partner_id, alias_name, name_normalized, source)
                   VALUES (?, ?, ?, 'import')""",
                (new_pm, raw["raw_name"], raw["name_normalized"])
            )
        db.execute(
            """UPDATE staging_partners
               SET decision='new', new_pm_id=?, resolved_at=datetime('now')
               WHERE id=?""",
            (new_pm, staging_id)
        )
        result_pm_id = new_pm
    else:
        return jsonify({"ok": False, "error": "Ismeretlen döntés"}), 400

    db.commit()

    # Return pending counts
    pending = query(
        """SELECT
             SUM(CASE WHEN zone='yellow' AND decision IS NULL THEN 1 ELSE 0 END) as py,
             SUM(CASE WHEN zone='red' AND decision IS NULL THEN 1 ELSE 0 END) as pr
           FROM staging_partners WHERE session_id=?""",
        (raw["session_id"],), one=True
    )

    return jsonify({
        "ok": True,
        "decision": decision,
        "pm_id": result_pm_id,
        "pending_yellow": pending["py"] or 0,
        "pending_red": pending["pr"] or 0,
    })


# ═══════════════════════════════════════════════════════════════════════
#  Step 3: Status Validation
# ═══════════════════════════════════════════════════════════════════════

NORMALIZED_STATUS_OPTIONS = [
    "PREPARATION", "QUOTED", "WON",
    "LOST_COMPETITOR", "LOST_CUSTOMER",
    "POSTPONED", "CLOSED_NO_RESPONSE",
    "NO_QUOTE", "NOT_RELEVANT", "ORDER_LINE",
]


@bp.route("/statuses/<session_id>", methods=["GET"])
def statuses(session_id):
    sess = _get_session(session_id)
    if not sess:
        flash("Ismeretlen session!", "error")
        return redirect(url_for("import_wizard.upload"))

    staging = query(
        "SELECT * FROM staging_statuses WHERE session_id=? ORDER BY quote_count DESC",
        (session_id,)
    )

    if not staging:
        # No unknown statuses — skip to issues
        execute(
            "UPDATE import_sessions SET status='issues' WHERE session_id=?",
            (session_id,)
        )
        flash("Minden státusz ismert — lépés kihagyva.", "success")
        return redirect(url_for("import_wizard.issues", session_id=session_id))

    return render_template(
        "import/statuses.html",
        session=sess,
        staging=staging,
        status_options=NORMALIZED_STATUS_OPTIONS,
        **_step_context(3, session_id),
    )


@bp.route("/statuses/<session_id>", methods=["POST"])
def statuses_post(session_id):
    db = get_db()

    for key, value in request.form.items():
        if key.startswith("norm_"):
            staging_id = key.replace("norm_", "")
            normalized = value
            add_to_dict = request.form.get(f"add_{staging_id}") == "on"

            db.execute(
                """UPDATE staging_statuses
                   SET suggested_norm=?, add_to_dict=?, resolved_at=datetime('now')
                   WHERE id=?""",
                (normalized, 1 if add_to_dict else 0, staging_id)
            )

            # Add to status dictionary if requested
            if add_to_dict and normalized:
                raw = db.execute(
                    "SELECT raw_status FROM staging_statuses WHERE id=?",
                    (staging_id,)
                ).fetchone()
                if raw:
                    flag_map = {
                        "PREPARATION": (1, 0, 0), "QUOTED": (1, 0, 0),
                        "WON": (0, 1, 0), "LOST_COMPETITOR": (0, 0, 1),
                        "LOST_CUSTOMER": (0, 0, 1), "POSTPONED": (0, 0, 0),
                        "CLOSED_NO_RESPONSE": (0, 0, 0), "NO_QUOTE": (0, 0, 0),
                        "NOT_RELEVANT": (0, 0, 0), "ORDER_LINE": (0, 0, 0),
                    }
                    flags = flag_map.get(normalized, (0, 0, 0))
                    try:
                        db.execute(
                            """INSERT OR IGNORE INTO status_dictionary
                               (raw_status, normalized, is_open, is_won, is_lost)
                               VALUES (?, ?, ?, ?, ?)""",
                            (raw["raw_status"], normalized, *flags)
                        )
                    except Exception:
                        pass  # duplicate, ignore

    db.commit()

    execute(
        "UPDATE import_sessions SET status='issues' WHERE session_id=?",
        (session_id,)
    )
    flash("Státuszok mentve.", "success")
    return redirect(url_for("import_wizard.issues", session_id=session_id))


# ═══════════════════════════════════════════════════════════════════════
#  Step 4: Issue List (Hiánylista)
# ═══════════════════════════════════════════════════════════════════════

@bp.route("/issues/<session_id>", methods=["GET"])
def issues(session_id):
    sess = _get_session(session_id)
    if not sess:
        flash("Ismeretlen session!", "error")
        return redirect(url_for("import_wizard.upload"))

    # Re-extract and transform to collect issues
    files_json = json.loads(sess["files_json"]) if sess["files_json"] else {}
    file_paths = {k: Path(v) for k, v in files_json.items()}

    try:
        raw_data, _ = etl_bridge.run_extract(file_paths)
        partner_lookup = etl_bridge.resolve_partners(session_id)
        transformed = etl_bridge.run_full_transform(raw_data, partner_lookup)
        issues_list = etl_bridge.collect_blocking_issues(transformed)
    except Exception as e:
        flash(f"Hiba a validáció során: {e}", "error")
        issues_list = []

    # Save issues to staging
    db = get_db()
    db.execute("DELETE FROM staging_issues WHERE session_id=?", (session_id,))
    for issue in issues_list:
        db.execute(
            """INSERT INTO staging_issues
               (session_id, severity, issue_type, quote_id, detail)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, issue["severity"], issue["issue_type"],
             issue.get("quote_id"), issue["detail"])
        )
    db.commit()

    # Load back with IDs
    blocking = query(
        """SELECT * FROM staging_issues
           WHERE session_id=? AND severity='blocking' AND overridden=0
           ORDER BY issue_type""",
        (session_id,)
    )
    warnings = query(
        """SELECT * FROM staging_issues
           WHERE session_id=? AND severity='warning'
           ORDER BY issue_type""",
        (session_id,)
    )
    overridden = query(
        """SELECT * FROM staging_issues
           WHERE session_id=? AND severity='blocking' AND overridden=1""",
        (session_id,)
    )

    can_proceed = len(blocking) == 0

    return render_template(
        "import/hianylist.html",
        session=sess,
        blocking=blocking,
        warnings=warnings,
        overridden=overridden,
        can_proceed=can_proceed,
        **_step_context(4, session_id),
    )


@bp.route("/issues/<session_id>", methods=["POST"])
def issues_post(session_id):
    db = get_db()
    action = request.form.get("action", "")

    if action == "override":
        issue_id = request.form.get("issue_id")
        reason = request.form.get("reason", "").strip()
        if not reason:
            # the form marks it required, but the server must enforce it too
            flash("Felülbíráláshoz indoklás szükséges.", "error")
            return redirect(url_for("import_wizard.issues", session_id=session_id))
        db.execute(
            """UPDATE staging_issues
               SET overridden=1, override_reason=?, resolved_at=datetime('now')
               WHERE id=?""",
            (reason, issue_id)
        )
        db.commit()
        return redirect(url_for("import_wizard.issues", session_id=session_id))

    if action == "next":
        # Check no unresolved blocking issues
        blocking = query(
            """SELECT COUNT(*) as cnt FROM staging_issues
               WHERE session_id=? AND severity='blocking' AND overridden=0""",
            (session_id,), one=True
        )
        if blocking and blocking["cnt"] > 0:
            flash("Blokkoló problémák megoldása szükséges!", "error")
            return redirect(url_for("import_wizard.issues", session_id=session_id))

        execute(
            "UPDATE import_sessions SET status='confirming' WHERE session_id=?",
            (session_id,)
        )
        return redirect(url_for("import_wizard.confirm", session_id=session_id))

    return redirect(url_for("import_wizard.issues", session_id=session_id))


# ═══════════════════════════════════════════════════════════════════════
#  Step 5: Confirmation
# ═══════════════════════════════════════════════════════════════════════

@bp.route("/confirm/<session_id>", methods=["GET"])
def confirm(session_id):
    sess = _get_session(session_id)
    if not sess:
        flash("Ismeretlen session!", "error")
        return redirect(url_for("import_wizard.upload"))

    # Gather summary stats
    partner_count = query(
        "SELECT COUNT(*) as cnt FROM staging_partners WHERE session_id=?",
        (session_id,), one=True
    )
    new_partners = query(
        "SELECT COUNT(*) as cnt FROM staging_partners WHERE session_id=? AND decision='new'",
        (session_id,), one=True
    )
    status_count = query(
        "SELECT COUNT(*) as cnt FROM staging_statuses WHERE session_id=?",
        (session_id,), one=True
    )
    blocking_count = query(
        "SELECT COUNT(*) as cnt FROM staging_issues WHERE session_id=? AND severity='blocking' AND overridden=0",
        (session_id,), one=True
    )
    warning_count = query(
        "SELECT COUNT(*) as cnt FROM staging_issues WHERE session_id=? AND severity='warning'",
        (session_id,), one=True
    )
    overridden_count = query(
        "SELECT COUNT(*) as cnt FROM staging_issues WHERE session_id=? AND severity='blocking' AND overridden=1",
        (session_id,), one=True
    )

    extract_summary = json.loads(sess["extract_summary"]) if sess["extract_summary"] else {}

    return render_template(
        "import/confirm.html",
        session=sess,
        extract_summary=extract_summary,
        partner_count=partner_count["cnt"] if partner_count else 0,
        new_partners=new_partners["cnt"] if new_partners else 0,
        status_count=status_count["cnt"] if status_count else 0,
        blocking_count=blocking_count["cnt"] if blocking_count else 0,
        warning_count=warning_count["cnt"] if warning_count else 0,
        overridden_count=overridden_count["cnt"] if overridden_count else 0,
        **_step_context(5, session_id),
    )


@bp.route("/confirm/<session_id>", methods=["POST"])
def confirm_post(session_id):
    action = request.form.get("action", "")

    if action == "abort":
        db = get_db()
        db.execute("DELETE FROM staging_partners WHERE session_id=?", (session_id,))
        db.execute("DELETE FROM staging_statuses WHERE session_id=?", (session_id,))
        db.execute("DELETE FROM staging_issues WHERE session_id=?", (session_id,))
        db.execute(
            "UPDATE import_sessions SET status='aborted', completed_at=datetime('now') WHERE session_id=?",
            (session_id,)
        )
        db.commit()
        flash("Import megszakítva.", "warning")
        return redirect(url_for("index"))

    if action == "commit":
        sess = _get_session(session_id)
        files_json = json.loads(sess["files_json"]) if sess["files_json"] else {}
        file_paths = {k: Path(v) for k, v in files_json.items()}

        try:
            # Full pipeline
            raw_data, _ = etl_bridge.run_extract(file_paths)
            partner_lookup = etl_bridge.resolve_partners(session_id)
            transformed = etl_bridge.run_full_transform(raw_data, partner_lookup)
            dashboard_path = etl_bridge.commit(transformed)

            # Update session
            execute(
                """UPDATE import_sessions
                   SET status='done', completed_at=datetime('now')
                   WHERE session_id=?""",
                (session_id,)
            )

            # Clean staging
            db = get_db()
            db.execute("DELETE FROM staging_partners WHERE session_id=?", (session_id,))
            db.execute("DELETE FROM staging_statuses WHERE session_id=?", (session_id,))
            db.execute("DELETE FROM staging_issues WHERE session_id=?", (session_id,))
            db.commit()

            flash(f"Dashboard sikeresen generálva: {dashboard_path}", "success")
        except Exception as e:
            flash(f"Hiba a deploy során: {e}", "error")
            return redirect(url_for("import_wizard.confirm", session_id=session_id))

        return redirect(url_for("index"))

    return redirect(url_for("import_wizard.confirm", session_id=session_id))
