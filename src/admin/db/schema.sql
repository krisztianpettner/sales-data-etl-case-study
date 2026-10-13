-- Admin DB schema (admin.db) — persistent operator knowledge
-- This database survives ETL rebuilds. dashboard.db is always derived.

-- ═══════════════════════════════════════════════════════════════════════
--  Partner master data (operator-maintained)
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS partner_master (
    partner_id      TEXT PRIMARY KEY,           -- PM-0001, PM-0002, ...
    display_name    TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    official_name   TEXT,
    country         TEXT,
    is_domestic     INTEGER,
    tax_id_hu       TEXT,                       -- HU adószám
    vat_eu          TEXT,                       -- EU VAT number
    partner_type    TEXT,                       -- viszonteladó / végfelhasználó
    industry        TEXT,
    teaor_code      TEXT,
    website         TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS partner_aliases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id      TEXT NOT NULL REFERENCES partner_master(partner_id),
    alias_name      TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    source          TEXT,                       -- 'extract', 'manual', 'fuzzy_merge'
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(partner_id, name_normalized)
);

CREATE TABLE IF NOT EXISTS partner_merges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    kept_id         TEXT NOT NULL REFERENCES partner_master(partner_id),
    merged_id       TEXT NOT NULL,              -- the PM-XXXX that was merged away
    merged_name     TEXT NOT NULL,
    reason          TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══════════════════════════════════════════════════════════════════════
--  Status dictionary (operator-extensible)
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS status_dictionary (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_status      TEXT NOT NULL UNIQUE,       -- exact raw text from Excel
    normalized      TEXT NOT NULL,              -- PREPARATION, QUOTED, WON, etc.
    is_open         INTEGER NOT NULL DEFAULT 0,
    is_won          INTEGER NOT NULL DEFAULT 0,
    is_lost         INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══════════════════════════════════════════════════════════════════════
--  Import session tracking
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS import_sessions (
    session_id      TEXT PRIMARY KEY,           -- UUID
    status          TEXT NOT NULL DEFAULT 'uploading',
                    -- uploading → partners → statuses → issues → confirming → done / aborted
    files_json      TEXT,                       -- JSON: {TG1_2025: "path", ...}
    extract_summary TEXT,                       -- JSON: {TG1_2025: {rows: N}, ...}
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT,
    notes           TEXT
);

-- ═══════════════════════════════════════════════════════════════════════
--  Staging tables (per-session, cleared on commit or abort)
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS staging_partners (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES import_sessions(session_id),
    raw_name        TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    match_score     REAL,                       -- 0.0 - 1.0
    matched_pm_id   TEXT,                       -- PM-XXXX if matched
    zone            TEXT NOT NULL,              -- 'green', 'yellow', 'red'
    decision        TEXT,                       -- 'accept', 'reassign', 'new', NULL (pending)
    new_pm_id       TEXT,                       -- if decision='new', newly created PM-XXXX
    source_file     TEXT,                       -- TG1_2025, TG2_2026, etc.
    occurrence_count INTEGER DEFAULT 1,
    resolved_at     TEXT,
    similarity      REAL DEFAULT 0.0,              -- best similarity to another red entry
    similar_to      TEXT DEFAULT ''                 -- raw_name of most similar red entry
);

CREATE TABLE IF NOT EXISTS staging_statuses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES import_sessions(session_id),
    raw_status      TEXT NOT NULL,
    quote_count     INTEGER DEFAULT 0,          -- how many quotes have this status
    suggested_norm  TEXT,                       -- operator picks from dropdown
    add_to_dict     INTEGER DEFAULT 1,          -- checkbox: add to status_dictionary
    resolved_at     TEXT
);

CREATE TABLE IF NOT EXISTS staging_issues (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES import_sessions(session_id),
    severity        TEXT NOT NULL,              -- 'blocking', 'warning'
    issue_type      TEXT NOT NULL,              -- 'won_no_work', 'partner_null', 'slow_reaction', etc.
    quote_id        TEXT,
    detail          TEXT NOT NULL,
    overridden      INTEGER DEFAULT 0,
    override_reason TEXT,
    resolved_at     TEXT
);

-- ═══════════════════════════════════════════════════════════════════════
--  Indexes
-- ═══════════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_aliases_partner   ON partner_aliases(partner_id);
CREATE INDEX IF NOT EXISTS idx_aliases_norm      ON partner_aliases(name_normalized);
CREATE INDEX IF NOT EXISTS idx_staging_p_session ON staging_partners(session_id);
CREATE INDEX IF NOT EXISTS idx_staging_s_session ON staging_statuses(session_id);
CREATE INDEX IF NOT EXISTS idx_staging_i_session ON staging_issues(session_id);
CREATE INDEX IF NOT EXISTS idx_pm_normalized     ON partner_master(name_normalized);
