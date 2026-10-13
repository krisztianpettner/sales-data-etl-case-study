"""
Flask admin application entry point.
"""
import sys
import sqlite3
import json
from pathlib import Path

# Add admin/ and etl/ to path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "etl"))

from flask import Flask, render_template, g, flash, redirect, url_for, request
from db.helpers import init_db, close_db, query

ADMIN_DIR = Path(__file__).resolve().parent
DASHBOARD_DB_PATH = ADMIN_DIR.parent / "etl" / "dashboard.db"


def create_app():
    app = Flask(
        __name__,
        template_folder=str(ADMIN_DIR / "templates"),
        static_folder=str(ADMIN_DIR / "static"),
    )
    app.secret_key = "admin-secret-key-change-in-prod"
    app.config["UPLOAD_FOLDER"] = str(ADMIN_DIR / "uploads")

    # Ensure upload folder exists
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    # Initialize DB
    init_db()

    # Register teardown
    app.teardown_appcontext(close_db)

    # Register blueprints (guarded imports — route files may not exist yet)
    try:
        from routes.import_wizard import bp as import_bp
        app.register_blueprint(import_bp)
    except ImportError as e:
        print(f"Warning: import_wizard blueprint not loaded: {e}")

    try:
        from routes.partners import bp as partners_bp
        app.register_blueprint(partners_bp)
    except ImportError as e:
        print(f"Warning: partners blueprint not loaded: {e}")

    try:
        from routes.status_dict import bp as status_bp
        app.register_blueprint(status_bp)
    except ImportError as e:
        print(f"Warning: status_dict blueprint not loaded: {e}")


    @app.route("/")
    def index():
        # Last import session
        last_session = query(
            "SELECT * FROM import_sessions ORDER BY started_at DESC LIMIT 1",
            one=True,
        )

        # Partner count
        partner_count_row = query(
            "SELECT COUNT(*) AS cnt FROM partner_master", one=True
        )
        partner_count = partner_count_row["cnt"] if partner_count_row else 0

        # Status dict count
        status_count_row = query(
            "SELECT COUNT(*) AS cnt FROM status_dictionary", one=True
        )
        status_count = status_count_row["cnt"] if status_count_row else 0

        # Quote counts from dashboard.db (may not exist yet)
        quote_total = None
        quote_tg1 = 0
        quote_tg2 = 0
        if DASHBOARD_DB_PATH.exists():
            try:
                conn = sqlite3.connect(str(DASHBOARD_DB_PATH))
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT product_line, COUNT(*) AS cnt FROM quotes GROUP BY product_line"
                ).fetchall()
                for r in rows:
                    if r["product_line"] == "TG1":
                        quote_tg1 = r["cnt"]
                    elif r["product_line"] == "TG2":
                        quote_tg2 = r["cnt"]
                quote_total = quote_tg1 + quote_tg2
                conn.close()
            except Exception:
                quote_total = None

        # Parse files_json for display
        last_files = None
        if last_session and last_session["files_json"]:
            try:
                last_files = json.loads(last_session["files_json"])
            except Exception:
                pass

        return render_template(
            "index.html",
            last_session=last_session,
            last_files=last_files,
            partner_count=partner_count,
            status_count=status_count,
            quote_total=quote_total,
            quote_tg1=quote_tg1,
            quote_tg2=quote_tg2,
        )

    @app.route("/regenerate")
    def regenerate():
        """Re-run export_json + generate_dashboard from existing dashboard.db."""
        if not DASHBOARD_DB_PATH.exists():
            flash("Nincs dashboard.db — először futtasson importot!", "error")
            return redirect(url_for("index"))

        import sys as _sys
        _etl = str(ADMIN_DIR.parent / "etl")
        if _etl not in _sys.path:
            _sys.path.insert(0, _etl)

        try:
            import export_json, generate_dashboard
            export_json.export()
            html = generate_dashboard.generate()
            out = ADMIN_DIR.parent / "dashboard.html"
            out.write_text(html, encoding="utf-8")
            flash(f"Dashboard újragenerálva: {out}", "success")
        except Exception as e:
            flash(f"Hiba a generálás során: {e}", "error")

        return redirect(url_for("index"))

    @app.route("/reset-dashboard", methods=["POST"])
    def reset_dashboard():
        """Delete dashboard.db, dashboard_data.json, and dashboard.html."""
        deleted = []
        dashboard_html = ADMIN_DIR.parent / "dashboard.html"
        data_json = ADMIN_DIR.parent / "data" / "dashboard_data.json"

        for path, label in [
            (DASHBOARD_DB_PATH, "dashboard.db"),
            (data_json, "dashboard_data.json"),
            (dashboard_html, "dashboard.html"),
        ]:
            if path.exists():
                path.unlink()
                deleted.append(label)

        if deleted:
            flash(f"Törölve: {', '.join(deleted)}", "success")
        else:
            flash("Nincs mit törölni — a fájlok már nem léteznek.", "info")

        return redirect(url_for("index"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000, threaded=True, use_reloader=False)
