"""Persistence for plugin state and error history (Phase 4).

Two tables, two responsibilities:

* ``installed_plugins`` records that a plugin exists and when it was last seen. The scan engine
  upserts every active plugin at the start of a scan, so ``last_seen`` is a reliable "when did
  we last actually load this?" without diffing manifests.
* ``plugin_errors`` records the underlying exception detail for anything captured as an ``ERROR``
  outcome by the scheduler. ``plugin_results.error`` gives the message; this gives the full
  traceback and the stage it happened in.

Statistics are not persisted -- they are queried live off ``plugin_results``, because a stale
statistics table would drift silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Any
import uuid

from ragstrike.database.connection import Database

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InstalledPlugin:
    slug: str
    name: str
    version: str
    category: str
    author: str
    source: str
    enabled: bool
    first_seen: datetime
    last_seen: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "version": self.version,
            "category": self.category,
            "author": self.author,
            "source": self.source,
            "enabled": self.enabled,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class PluginStatistics:
    slug: str
    total_runs: int
    passed: int
    failed: int
    #: Ran cleanly but reached no verdict (Phase 6). Counted separately from ``errored`` because
    #: an undetermined result and a broken one need different follow-up.
    inconclusive: int
    errored: int
    skipped: int
    avg_elapsed_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "total_runs": self.total_runs,
            "passed": self.passed,
            "failed": self.failed,
            "inconclusive": self.inconclusive,
            "errored": self.errored,
            "skipped": self.skipped,
            "avg_elapsed_ms": round(self.avg_elapsed_ms, 2),
        }


_UPSERT_INSTALLED = """
INSERT INTO installed_plugins (
    slug, name, version, category, author, source, enabled, first_seen, last_seen
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(slug) DO UPDATE SET
    name = excluded.name,
    version = excluded.version,
    category = excluded.category,
    author = excluded.author,
    source = excluded.source,
    enabled = excluded.enabled,
    last_seen = excluded.last_seen
"""

_INSERT_ERROR = """
INSERT INTO plugin_errors (
    id, scan_id, slug, plugin_version, stage, error_class, message, traceback, occurred_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class PluginRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def upsert(
        self,
        *,
        slug: str,
        name: str,
        version: str,
        category: str,
        author: str,
        source: str,
        enabled: bool = True,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        async with self.database.connect() as conn:
            await conn.execute(
                _UPSERT_INSTALLED,
                (slug, name, version, category, author, source, int(enabled), now, now),
            )

    async def list_installed(self) -> list[InstalledPlugin]:
        async with self.database.connect() as conn:
            cursor = await conn.execute("SELECT * FROM installed_plugins ORDER BY slug")
            rows = await cursor.fetchall()
        return [_installed_from_row(row) for row in rows]

    async def record_error(
        self,
        *,
        slug: str,
        scan_id: str = "",
        plugin_version: str = "",
        stage: str = "",
        error_class: str = "",
        message: str = "",
        traceback_text: str = "",
    ) -> None:
        """Append one error record. Never overwrites -- the table is an audit log."""
        async with self.database.connect() as conn:
            await conn.execute(
                _INSERT_ERROR,
                (
                    uuid.uuid4().hex,
                    scan_id,
                    slug,
                    plugin_version,
                    stage,
                    error_class,
                    message,
                    traceback_text,
                    datetime.now(UTC).isoformat(),
                ),
            )

    async def statistics(self) -> list[PluginStatistics]:
        """Aggregate outcomes across every scan, per plugin.

        Queried live rather than materialised, because a stale statistics table would drift
        silently.
        """
        async with self.database.connect() as conn:
            cursor = await conn.execute("""
                SELECT
                    plugin_slug AS slug,
                    COUNT(*) AS total_runs,
                    SUM(CASE outcome WHEN 'PASS' THEN 1 ELSE 0 END) AS passed,
                    SUM(CASE outcome WHEN 'FAIL' THEN 1 ELSE 0 END) AS failed,
                    SUM(CASE outcome WHEN 'INCONCLUSIVE' THEN 1 ELSE 0 END) AS inconclusive,
                    SUM(CASE outcome WHEN 'ERROR' THEN 1 ELSE 0 END) AS errored,
                    SUM(CASE outcome WHEN 'SKIPPED' THEN 1 ELSE 0 END) AS skipped,
                    COALESCE(AVG(elapsed_ms), 0) AS avg_elapsed_ms
                FROM plugin_results
                GROUP BY plugin_slug
                ORDER BY plugin_slug
                """)
            rows = await cursor.fetchall()
        return [
            PluginStatistics(
                slug=row["slug"],
                total_runs=int(row["total_runs"] or 0),
                passed=int(row["passed"] or 0),
                failed=int(row["failed"] or 0),
                inconclusive=int(row["inconclusive"] or 0),
                errored=int(row["errored"] or 0),
                skipped=int(row["skipped"] or 0),
                avg_elapsed_ms=float(row["avg_elapsed_ms"] or 0.0),
            )
            for row in rows
        ]

    async def error_count(self, slug: str | None = None) -> int:
        query = "SELECT COUNT(*) AS n FROM plugin_errors"
        params: tuple[Any, ...] = ()
        if slug is not None:
            query += " WHERE slug = ?"
            params = (slug,)
        async with self.database.connect() as conn:
            cursor = await conn.execute(query, params)
            row = await cursor.fetchone()
        return int(row["n"]) if row else 0


def _installed_from_row(row: Any) -> InstalledPlugin:
    return InstalledPlugin(
        slug=row["slug"],
        name=row["name"],
        version=row["version"],
        category=row["category"],
        author=row["author"],
        source=row["source"],
        enabled=bool(row["enabled"]),
        first_seen=datetime.fromisoformat(row["first_seen"]),
        last_seen=datetime.fromisoformat(row["last_seen"]),
    )
