"""aiosqlite connection management.

One connection per unit of work, opened through an async context manager. SQLite is fast enough that
pooling would be premature, and a connection per transaction keeps boundaries obvious.

**No vectors here, ever.** SQLite has no vector index; storing embeddings would mean full scans over
float blobs, which is the worst of both stores. This database holds scan history and results.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from pathlib import Path

import aiosqlite

from ragstrike.core.errors import PersistenceError

log = logging.getLogger(__name__)


class Database:
    """Owns the database file and hands out configured connections."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        """Yield a configured connection, committing on clean exit, rolling back on error."""
        try:
            connection = await aiosqlite.connect(self.path)
        except Exception as exc:
            raise PersistenceError(
                f"Could not open the database at {self.path}: {exc}",
                hint="Check directory permissions, or delete the file to start fresh.",
            ) from exc

        connection.row_factory = aiosqlite.Row
        try:
            await connection.execute("PRAGMA foreign_keys = ON")
            await connection.execute("PRAGMA journal_mode = WAL")
            await connection.execute("PRAGMA busy_timeout = 5000")
            yield connection
            await connection.commit()
        except Exception:
            await connection.rollback()
            raise
        finally:
            await connection.close()

    async def healthy(self) -> tuple[bool, str]:
        """Cheap liveness probe. Never raises."""
        try:
            async with self.connect() as conn:
                await conn.execute("SELECT 1")
            return True, ""
        except Exception as exc:
            return False, str(exc)
