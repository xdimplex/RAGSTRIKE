"""Table definitions.

Three tables in Phase 3: ``targets``, ``scan_sessions``, ``plugin_results``. Reports arrive in
Phase 6 and get their own table then.

``config_snapshot`` on ``scan_sessions`` is worth noting. It stores the fully merged configuration
that produced the scan, so a result from six months ago can still be explained -- "why did this run
skip four plugins" is answerable without guessing what the YAML said at the time.
"""

from __future__ import annotations

TARGETS = """
CREATE TABLE IF NOT EXISTS targets (
    id                 TEXT PRIMARY KEY,
    name               TEXT NOT NULL UNIQUE,
    adapter            TEXT NOT NULL,
    url                TEXT NOT NULL,
    timeout_s          INTEGER NOT NULL DEFAULT 60,
    enabled            INTEGER NOT NULL DEFAULT 1,
    capabilities       TEXT NOT NULL DEFAULT '[]',
    options            TEXT NOT NULL DEFAULT '{}',
    authorized_by      TEXT NOT NULL DEFAULT '',
    authorization_ref  TEXT NOT NULL DEFAULT '',
    authorization_scope TEXT NOT NULL DEFAULT '',
    authorized_at      TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL
)
"""

SCAN_SESSIONS = """
CREATE TABLE IF NOT EXISTS scan_sessions (
    id                TEXT PRIMARY KEY,
    target_id         TEXT NOT NULL,
    target_name       TEXT NOT NULL,
    state             TEXT NOT NULL,
    engine_version    TEXT NOT NULL DEFAULT '',
    plugin_inventory  TEXT NOT NULL DEFAULT '{}',
    config_snapshot   TEXT NOT NULL DEFAULT '{}',
    started_at        TEXT NOT NULL,
    finished_at       TEXT,
    plugins_total     INTEGER NOT NULL DEFAULT 0,
    plugins_executed  INTEGER NOT NULL DEFAULT 0,
    plugins_passed    INTEGER NOT NULL DEFAULT 0,
    plugins_failed    INTEGER NOT NULL DEFAULT 0,
    plugins_errored   INTEGER NOT NULL DEFAULT 0,
    plugins_skipped   INTEGER NOT NULL DEFAULT 0,
    error             TEXT NOT NULL DEFAULT ''
)
"""

PLUGIN_RESULTS = """
CREATE TABLE IF NOT EXISTS plugin_results (
    id                TEXT PRIMARY KEY,
    scan_id           TEXT NOT NULL,
    plugin_slug       TEXT NOT NULL,
    plugin_version    TEXT NOT NULL DEFAULT '',
    outcome           TEXT NOT NULL,
    summary           TEXT NOT NULL DEFAULT '',
    detail            TEXT NOT NULL DEFAULT '',
    recommendation    TEXT NOT NULL DEFAULT '',
    payloads_executed INTEGER NOT NULL DEFAULT 0,
    elapsed_ms        INTEGER NOT NULL DEFAULT 0,
    error             TEXT NOT NULL DEFAULT '',
    evidence          TEXT NOT NULL DEFAULT '{}',
    created_at        TEXT NOT NULL,
    FOREIGN KEY (scan_id) REFERENCES scan_sessions (id) ON DELETE CASCADE
)
"""

SCHEMA_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""

INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_scans_target ON scan_sessions (target_id, started_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_scans_state ON scan_sessions (state)",
    "CREATE INDEX IF NOT EXISTS idx_results_scan ON plugin_results (scan_id)",
    "CREATE INDEX IF NOT EXISTS idx_results_outcome ON plugin_results (scan_id, outcome)",
]

ALL_TABLES = [TARGETS, SCAN_SESSIONS, PLUGIN_RESULTS, SCHEMA_MIGRATIONS]


# ================================================================================================
# Phase 4 additions.
#
# `plugin_results` (Phase 3) is the per-scan per-plugin outcome. Phase 4 adds two neighbours:
#
#   installed_plugins   -- one row per unique slug ever seen. Tracks first_seen/last_seen and the
#                          current version so a "plugin was added between scans" event is visible
#                          without diffing manifests.
#   plugin_errors       -- append-only log of plugin failures. Distinct from plugin_results,
#                          which records the OUTCOME (ERROR is one of them). This table records
#                          the underlying exception detail with traceback, so a bug report has
#                          more than "ERROR" to attach.
#
# Statistics are queried live from plugin_results rather than materialised into a table: the
# schema is small, and a stale statistics table would drift silently.
# ================================================================================================

INSTALLED_PLUGINS = """
CREATE TABLE IF NOT EXISTS installed_plugins (
    slug          TEXT PRIMARY KEY,
    name          TEXT NOT NULL DEFAULT '',
    version       TEXT NOT NULL DEFAULT '',
    category      TEXT NOT NULL DEFAULT '',
    author        TEXT NOT NULL DEFAULT '',
    source        TEXT NOT NULL DEFAULT '',
    enabled       INTEGER NOT NULL DEFAULT 1,
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL
)
"""

PLUGIN_ERRORS = """
CREATE TABLE IF NOT EXISTS plugin_errors (
    id          TEXT PRIMARY KEY,
    scan_id     TEXT NOT NULL DEFAULT '',
    slug        TEXT NOT NULL,
    plugin_version TEXT NOT NULL DEFAULT '',
    stage       TEXT NOT NULL DEFAULT '',
    error_class TEXT NOT NULL DEFAULT '',
    message     TEXT NOT NULL DEFAULT '',
    traceback   TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL
)
"""

PHASE4_TABLES = [INSTALLED_PLUGINS, PLUGIN_ERRORS]

PHASE4_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_installed_last_seen ON installed_plugins (last_seen DESC)",
    "CREATE INDEX IF NOT EXISTS idx_plugin_errors_slug ON plugin_errors (slug, occurred_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_plugin_errors_scan ON plugin_errors (scan_id)",
]


# ================================================================================================
# Phase 10 additions.
#
# `findings` is the Analyzer Engine's output, and it is a DIFFERENT THING from `plugin_results`.
#
#   plugin_results  -- what a plugin observed and concluded. Written by the scheduler.
#   findings        -- what the ANALYZER concluded from those observations, graded against a
#                      versioned rule set. Written by the analyzer.
#
# Keeping them separate is what makes re-analysis possible: rules change, so the same stored
# observations can be re-graded later and produce a second, differently-versioned finding without
# rewriting history. A single merged table would force every rule change to mutate the record of
# what was actually observed.
#
# `analyzer_version` and `rules_version` are on every row for the same reason a scan records its
# scoring model: a finding is only interpretable against the logic that produced it.
# ================================================================================================

FINDINGS = """
CREATE TABLE IF NOT EXISTS findings (
    id               TEXT PRIMARY KEY,
    scan_id          TEXT NOT NULL,
    plugin_id        TEXT NOT NULL,
    category         TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL,
    severity         TEXT NOT NULL DEFAULT 'INFO',
    confidence       REAL NOT NULL DEFAULT 0.0,
    confidence_band  TEXT NOT NULL DEFAULT 'low',
    risk_score       REAL NOT NULL DEFAULT 0.0,
    evidence         TEXT NOT NULL DEFAULT '{}',
    recommendation   TEXT NOT NULL DEFAULT '',
    references_json  TEXT NOT NULL DEFAULT '[]',
    notes            TEXT NOT NULL DEFAULT '',
    analyzer_version TEXT NOT NULL DEFAULT '',
    metadata         TEXT NOT NULL DEFAULT '{}',
    created_at       TEXT NOT NULL
)
"""

PHASE10_TABLES = [FINDINGS]

PHASE10_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_findings_scan ON findings (scan_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_findings_status ON findings (scan_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_findings_category ON findings (category, severity)",
]


# ================================================================================================
# Phase 11 additions.
#
# `reports` stores report METADATA and the rendered document; `report_exports` is an append-only
# log of files written to disk.
#
# WHY THE RENDERED CONTENT IS STORED, NOT JUST THE MODEL. A report is an artifact someone made a
# decision from. Regenerating it later from findings would produce a different document the moment
# a template, a renderer, or the report version changes -- and "what did the report actually say in
# March" is exactly the question an audit asks. The stored content is the answer.
#
# `report_exports` is separate because one report is exported many times, to many formats and
# paths, and folding that into `reports` would either lose history or duplicate the content.
# ================================================================================================

REPORTS = """
CREATE TABLE IF NOT EXISTS reports (
    id             TEXT PRIMARY KEY,
    scan_id        TEXT NOT NULL,
    title          TEXT NOT NULL DEFAULT '',
    target         TEXT NOT NULL DEFAULT '',
    format         TEXT NOT NULL DEFAULT 'json',
    content        TEXT NOT NULL DEFAULT '',
    summary        TEXT NOT NULL DEFAULT '{}',
    finding_count  INTEGER NOT NULL DEFAULT 0,
    risk_score     REAL NOT NULL DEFAULT 0.0,
    status         TEXT NOT NULL DEFAULT '',
    report_version TEXT NOT NULL DEFAULT '',
    analyzer_version TEXT NOT NULL DEFAULT '',
    framework_version TEXT NOT NULL DEFAULT '',
    generated_at   TEXT NOT NULL
)
"""

REPORT_EXPORTS = """
CREATE TABLE IF NOT EXISTS report_exports (
    id          TEXT PRIMARY KEY,
    report_id   TEXT NOT NULL,
    scan_id     TEXT NOT NULL DEFAULT '',
    format      TEXT NOT NULL,
    path        TEXT NOT NULL DEFAULT '',
    size_bytes  INTEGER NOT NULL DEFAULT 0,
    exported_at TEXT NOT NULL
)
"""

PHASE11_TABLES = [REPORTS, REPORT_EXPORTS]

PHASE11_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_reports_scan ON reports (scan_id, generated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_report_exports_report ON report_exports (report_id)",
]
