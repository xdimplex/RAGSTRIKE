"""Operator-adjustable settings that survive a restart.

A deliberately small key/value store. It holds *operational* preferences -- default ``top_k``,
whether the Chat page shows the model's raw output -- and nothing else.

**No security control is ever stored here.** Controls are composed in ``profiles/*/profile.py``, in
code. A value in a database that could silently harden the vulnerable target would invalidate every
scan result with no visible symptom (ADR-009), and a database row is exactly the kind of thing that
gets changed by accident.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from database.connection import Database

log = logging.getLogger(__name__)


class SettingsRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def get(self, key: str, default: Any = None) -> Any:
        async with self.database.connect() as conn:
            cursor = await conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = await cursor.fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return row["value"]

    async def set(self, key: str, value: Any) -> None:
        async with self.database.connect() as conn:
            await conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, json.dumps(value), datetime.now(UTC).isoformat()),
            )
        log.info("setting updated", extra={"key": key})

    async def all(self) -> dict[str, Any]:
        async with self.database.connect() as conn:
            cursor = await conn.execute("SELECT key, value FROM app_settings ORDER BY key")
            rows = await cursor.fetchall()
        result: dict[str, Any] = {}
        for row in rows:
            try:
                result[row["key"]] = json.loads(row["value"])
            except json.JSONDecodeError:
                result[row["key"]] = row["value"]
        return result
