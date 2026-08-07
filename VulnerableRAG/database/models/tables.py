"""Table definitions.

Four tables, and a hard rule: **no vectors here.** SQLite has no vector index, so embeddings stored
in it mean full table scans over float blobs. Vectors live in ChromaDB; this database holds the
metadata that describes them.

``documents.pdf_metadata`` is worth noting. It stores the PDF's own metadata fields verbatim as JSON.
Those fields are an ingestion surface -- invisible when a human opens the file, but read by the
extractor -- so keeping them queryable makes a metadata-injection exercise inspectable after the fact.
"""

from __future__ import annotations

#: Documents that have been ingested. One row per successful upload.
DOCUMENTS = """
CREATE TABLE IF NOT EXISTS documents (
    id                TEXT PRIMARY KEY,
    original_filename TEXT NOT NULL,
    stored_filename   TEXT NOT NULL,
    content_type      TEXT NOT NULL,
    size_bytes        INTEGER NOT NULL,
    page_count        INTEGER NOT NULL,
    chunk_count       INTEGER NOT NULL,
    sha256            TEXT NOT NULL,
    uploaded_at       TEXT NOT NULL,
    pdf_metadata      TEXT NOT NULL DEFAULT '{}'
)
"""

#: Append-only audit of what happened to each document.
UPLOAD_HISTORY = """
CREATE TABLE IF NOT EXISTS upload_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL,
    filename    TEXT NOT NULL,
    action      TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL
)
"""

#: Operator-adjustable values that outlive a process restart.
SETTINGS = """
CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

#: Applied migrations, so the runner knows where it left off.
SCHEMA_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""

INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_documents_uploaded_at ON documents (uploaded_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_history_document_id ON upload_history (document_id)",
    "CREATE INDEX IF NOT EXISTS idx_history_occurred_at ON upload_history (occurred_at DESC)",
]

ALL_TABLES = [DOCUMENTS, UPLOAD_HISTORY, SETTINGS, SCHEMA_MIGRATIONS]
