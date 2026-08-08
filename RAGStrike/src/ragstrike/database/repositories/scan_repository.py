"""Scan session and plugin result persistence.

Returns domain entities, never rows. Nothing outside this package sees an ``aiosqlite.Row``.

The engine writes a scan record *before* it runs anything and updates it as the state machine
advances, so a process killed mid-scan leaves a visible non-terminal row rather than nothing at all.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
import json
import logging
from typing import Any

from ragstrike.database.connection import Database
from ragstrike.models.entities.scan import PluginResult, ScanSession
from ragstrike.models.values.enums import PluginOutcome, ScanState

log = logging.getLogger(__name__)

_INSERT_SCAN = """
INSERT INTO scan_sessions (
    id, target_id, target_name, name, profile, state, engine_version, plugin_inventory,
    config_snapshot, started_at, finished_at, plugins_total, plugins_executed, plugins_passed,
    plugins_failed, plugins_errored, plugins_skipped, error
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_UPDATE_SCAN = """
UPDATE scan_sessions SET
    state = ?, plugin_inventory = ?, finished_at = ?, plugins_total = ?, plugins_executed = ?,
    plugins_passed = ?, plugins_failed = ?, plugins_errored = ?, plugins_skipped = ?, error = ?
WHERE id = ?
"""

_INSERT_RESULT = """
INSERT INTO plugin_results (
    id, scan_id, plugin_slug, plugin_version, outcome, summary, detail, recommendation,
    payloads_executed, elapsed_ms, error, evidence, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class ScanRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    # -- scans ------------------------------------------------------------------------------

    async def create(self, scan: ScanSession, *, config_snapshot: dict[str, Any]) -> None:
        async with self.database.connect() as conn:
            await conn.execute(
                _INSERT_SCAN,
                (
                    scan.id,
                    scan.target_id,
                    scan.target_name,
                    scan.name,
                    scan.profile,
                    scan.state.value,
                    scan.engine_version,
                    json.dumps(scan.plugin_inventory),
                    json.dumps(config_snapshot),
                    scan.started_at.isoformat(),
                    scan.finished_at.isoformat() if scan.finished_at else None,
                    scan.plugins_total,
                    scan.plugins_executed,
                    scan.plugins_passed,
                    scan.plugins_failed,
                    scan.plugins_errored,
                    scan.plugins_skipped,
                    scan.error,
                ),
            )
        log.info("scan session created", extra={"scan_id": scan.id, "target": scan.target_name})

    async def update(self, scan: ScanSession) -> None:
        async with self.database.connect() as conn:
            await conn.execute(
                _UPDATE_SCAN,
                (
                    scan.state.value,
                    json.dumps(scan.plugin_inventory),
                    scan.finished_at.isoformat() if scan.finished_at else None,
                    scan.plugins_total,
                    scan.plugins_executed,
                    scan.plugins_passed,
                    scan.plugins_failed,
                    scan.plugins_errored,
                    scan.plugins_skipped,
                    scan.error,
                    scan.id,
                ),
            )

    async def get(self, scan_id: str) -> ScanSession | None:
        async with self.database.connect() as conn:
            cursor = await conn.execute("SELECT * FROM scan_sessions WHERE id = ?", (scan_id,))
            row = await cursor.fetchone()
        return _scan_from_row(row) if row else None

    async def list_recent(self, limit: int = 20) -> list[ScanSession]:
        async with self.database.connect() as conn:
            cursor = await conn.execute(
                "SELECT * FROM scan_sessions ORDER BY started_at DESC LIMIT ?", (limit,)
            )
            rows = await cursor.fetchall()
        return [_scan_from_row(row) for row in rows]

    async def count(self) -> int:
        async with self.database.connect() as conn:
            cursor = await conn.execute("SELECT COUNT(*) AS n FROM scan_sessions")
            row = await cursor.fetchone()
        return int(row["n"]) if row else 0

    # -- results ----------------------------------------------------------------------------

    async def add_results(self, results: Sequence[PluginResult]) -> None:
        if not results:
            return
        async with self.database.connect() as conn:
            await conn.executemany(
                _INSERT_RESULT,
                [
                    (
                        r.id,
                        r.scan_id,
                        r.plugin_slug,
                        r.plugin_version,
                        r.outcome.value,
                        r.summary,
                        r.detail,
                        r.recommendation,
                        r.payloads_executed,
                        r.elapsed_ms,
                        r.error,
                        json.dumps(r.evidence),
                        r.created_at.isoformat(),
                    )
                    for r in results
                ],
            )
        log.info("plugin results stored", extra={"count": len(results)})

    async def results_for(self, scan_id: str) -> list[PluginResult]:
        async with self.database.connect() as conn:
            cursor = await conn.execute(
                "SELECT * FROM plugin_results WHERE scan_id = ? ORDER BY created_at", (scan_id,)
            )
            rows = await cursor.fetchall()
        return [_result_from_row(row) for row in rows]


def _scan_from_row(row: Any) -> ScanSession:
    return ScanSession(
        id=row["id"],
        target_id=row["target_id"],
        target_name=row["target_name"],
        name=_optional(row, "name"),
        profile=_optional(row, "profile"),
        state=ScanState(row["state"]),
        engine_version=row["engine_version"],
        plugin_inventory=json.loads(row["plugin_inventory"] or "{}"),
        started_at=datetime.fromisoformat(row["started_at"]),
        finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
        plugins_total=row["plugins_total"],
        plugins_executed=row["plugins_executed"],
        plugins_passed=row["plugins_passed"],
        plugins_failed=row["plugins_failed"],
        plugins_errored=row["plugins_errored"],
        plugins_skipped=row["plugins_skipped"],
        error=row["error"],
    )


def _optional(row: Any, column: str) -> str:
    """Read a column that may not exist yet, as a string.

    Rows written before migration 5 have no ``name`` or ``profile``, and a database that predates a
    migration should read as "empty" rather than raise.

    ``row.keys()`` is deliberate and must not be simplified to ``column in row``: a ``sqlite3.Row``
    iterates its VALUES, so the shorter form asks whether any cell equals "name" -- a different
    question with an occasionally identical answer, which is the worst kind of bug.
    """
    return (row[column] if column in row.keys() else "") or ""  # noqa: SIM118 - see above


def _result_from_row(row: Any) -> PluginResult:
    return PluginResult(
        id=row["id"],
        scan_id=row["scan_id"],
        plugin_slug=row["plugin_slug"],
        plugin_version=row["plugin_version"],
        outcome=PluginOutcome(row["outcome"]),
        summary=row["summary"],
        detail=row["detail"],
        recommendation=row["recommendation"],
        payloads_executed=row["payloads_executed"],
        elapsed_ms=row["elapsed_ms"],
        error=row["error"],
        evidence=json.loads(row["evidence"] or "{}"),
        created_at=datetime.fromisoformat(row["created_at"]),
    )
