"""aiosqlite connection management.

One connection per request, opened through an async context manager. SQLite is fast enough that
pooling would be premature here, and a connection per request keeps transaction boundaries obvious.

Pragmas are set on every connection:

* ``foreign_keys=ON`` -- SQLite disables these by default, which surprises people.
* ``journal_mode=WAL`` -- readers do not block the writer, so the UI stays responsive during
  ingestion.
* ``busy_timeout`` -- avoids spurious "database is locked" when an upload and a page refresh collide.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

log = logging.getLogger(__name__)


class Database:
    """Owns the database file and hands out connections."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        """Yield a configured connection, committing on clean exit."""
        connection = await aiosqlite.connect(self.path)
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
        """Cheap liveness probe for ``GET /health``. Never raises."""
        try:
            async with self.connect() as conn:
                await conn.execute("SELECT 1")
            return True, ""
        except Exception as exc:  # noqa: BLE001 - a health check reports, it does not propagate
            return False, str(exc)
