"""Forward-only migration runner.

Numbered, recorded, applied in order. There are no down-migrations: a rollback path that is never
exercised is a trap, and the SDD says so explicitly.

Migrations are immutable once released. Correcting one means writing the next.
"""

from __future__ import annotations

from datetime import UTC, datetime
import logging

from ragstrike.database.connection import Database
from ragstrike.database.models.tables import (
    ALL_TABLES,
    INDICES,
    PHASE4_INDICES,
    PHASE4_TABLES,
    PHASE10_INDICES,
    PHASE10_TABLES,
    PHASE11_INDICES,
    PHASE11_TABLES,
    SCHEMA_MIGRATIONS,
)

log = logging.getLogger(__name__)

#: ``(version, name, [statements])``, applied in ascending order.
#:
#: New migrations are appended, never inserted. Migration ledgers are ordered by version, and
#: inserting between released numbers would silently reapply already-recorded work.
MIGRATIONS: list[tuple[int, str, list[str]]] = [
    (1, "initial_schema", [*ALL_TABLES, *INDICES]),
    (2, "plugin_tables", [*PHASE4_TABLES, *PHASE4_INDICES]),
    (3, "analyzer_findings", [*PHASE10_TABLES, *PHASE10_INDICES]),
    (4, "reports", [*PHASE11_TABLES, *PHASE11_INDICES]),
]


async def run_migrations(database: Database) -> list[int]:
    """Apply pending migrations. Returns the versions applied on this call."""
    applied: list[int] = []

    async with database.connect() as conn:
        # Bootstrap: the ledger has to exist before it can be read.
        await conn.execute(SCHEMA_MIGRATIONS)
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
            # Not "name": `extra` keys colliding with LogRecord attributes raise at the call site.
            log.info("migration applied", extra={"version": version, "migration": name})

    if not applied:
        log.debug("schema up to date")
    return applied
