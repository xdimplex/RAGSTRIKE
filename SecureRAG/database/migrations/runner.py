"""Forward-only migration runner.

Migrations are numbered, applied in order, and recorded in ``schema_migrations``. There are no
down-migrations: a rollback path that is never exercised is a trap, and this is a lab whose database
can be deleted and rebuilt in seconds.

Phase 2 ships one migration, expressed as Python statements from ``database/models/tables.py`` rather
than a ``.sql`` file, so that the schema and the row mappers sit next to each other and cannot drift.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from database.connection import Database
from database.models.tables import ALL_TABLES, INDICES

log = logging.getLogger(__name__)

#: ``(version, name, [statements])``, applied in ascending version order.
MIGRATIONS: list[tuple[int, str, list[str]]] = [
    (1, "initial_schema", [*ALL_TABLES, *INDICES]),
]


async def run_migrations(database: Database) -> list[int]:
    """Apply any pending migrations. Returns the versions applied this run."""
    applied: list[int] = []

    async with database.connect() as conn:
        # Bootstrap: the ledger must exist before it can be read.
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    INTEGER PRIMARY KEY,
                name       TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """)
        cursor = await conn.execute("SELECT version FROM schema_migrations")
        done = {row["version"] for row in await cursor.fetchall()}

        for version, name, statements in MIGRATIONS:
            if version in done:
                continue
            for statement in statements:
                await conn.execute(statement)
            await conn.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, datetime.now(UTC).isoformat()),
            )
            applied.append(version)
            # Not "name": `extra` keys that collide with LogRecord attributes raise at log time.
            log.info("migration applied", extra={"version": version, "migration": name})

    if not applied:
        log.debug("schema up to date")
    return applied
