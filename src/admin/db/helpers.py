"""
Database helpers for the admin interface.
Manages connections to admin.db (persistent) and dashboard.db (rebuilt).
"""
import sqlite3
from pathlib import Path
from flask import g

ADMIN_DB_PATH = Path(__file__).resolve().parent.parent.parent / "admin" / "admin.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_db():
    """Get or create a connection to admin.db for the current request."""
    if "admin_db" not in g:
        g.admin_db = sqlite3.connect(str(ADMIN_DB_PATH), timeout=10)
        g.admin_db.row_factory = sqlite3.Row
        g.admin_db.execute("PRAGMA journal_mode=WAL")
        g.admin_db.execute("PRAGMA busy_timeout=5000")
        g.admin_db.execute("PRAGMA foreign_keys=ON")
    return g.admin_db


def close_db(e=None):
    """Close admin.db connection at end of request."""
    db = g.pop("admin_db", None)
    if db is not None:
        db.close()


def init_db():
    """Initialize admin.db schema from schema.sql."""
    ADMIN_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(ADMIN_DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    db.executescript(schema_sql)
    db.commit()
    db.close()


def query(sql, params=(), one=False):
    """Execute a query on admin.db and return results as list of Row objects."""
    db = get_db()
    cur = db.execute(sql, params)
    rows = cur.fetchall()
    return rows[0] if one and rows else rows if not one else None


def execute(sql, params=()):
    """Execute a write statement on admin.db and return lastrowid."""
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    return cur.lastrowid


def executemany(sql, params_list):
    """Execute a write statement with many parameter sets."""
    db = get_db()
    db.executemany(sql, params_list)
    db.commit()


def next_partner_id():
    """Generate the next PM-XXXX partner ID."""
    db = get_db()
    row = db.execute(
        "SELECT partner_id FROM partner_master ORDER BY partner_id DESC LIMIT 1"
    ).fetchone()
    if row:
        num = int(row["partner_id"].replace("PM-", "")) + 1
    else:
        num = 1
    return f"PM-{num:04d}"
