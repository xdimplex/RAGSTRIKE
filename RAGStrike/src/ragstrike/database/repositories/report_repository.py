"""Persistence for generated reports and their export history.

Implements the :class:`~ragstrike.reporters.base.renderer.ReportRepository` port. ``reporters`` sits
below ``database`` in the layer contract, so the dependency points this way -- report generation
stays a pure transformation and is testable with no database attached.

**The rendered content is stored, not just the model.** A report is an artifact someone made a
decision from; regenerating it later would produce a different document the moment a template or
renderer changed, and "what did the report actually say in March" is exactly what an audit asks.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from typing import Any
import uuid

from ragstrike.database.connection import Database
from ragstrike.reporters.base.record import StoredReport

log = logging.getLogger(__name__)

_INSERT_REPORT = """
INSERT INTO reports (
    id, scan_id, title, target, format, content, summary, finding_count, risk_score,
    status, report_version, analyzer_version, framework_version, generated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_EXPORT = """
INSERT INTO report_exports (id, report_id, scan_id, format, path, size_bytes, exported_at)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""


#: The persistence payload is defined by ``reporters``, on the lower layer, so that package never
#: needs to import this one. Aliased here because "ReportRecord" reads better at the call sites in
#: this module, and because the name was already in use before the port moved.
ReportRecord = StoredReport


class ReportRepository:
    """Reads and writes report metadata, content, and export history."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def save_report(self, record: ReportRecord) -> None:
        async with self.database.connect() as conn:
            await conn.execute(
                _INSERT_REPORT,
                (
                    record.id,
                    record.scan_id,
                    record.title,
                    record.target,
                    record.fmt,
                    record.content,
                    json.dumps(record.summary, default=str),
                    record.finding_count,
                    float(record.risk_score),
                    record.status,
                    record.report_version,
                    record.analyzer_version,
                    record.framework_version,
                    record.generated_at.isoformat(),
                ),
            )
            await conn.commit()
        log.info(
            "report stored",
            extra={"report_id": record.id, "scan_id": record.scan_id, "format": record.fmt},
        )

    async def list_reports(self, scan_id: str = "") -> list[ReportRecord]:
        """Reports, newest first. All of them when *scan_id* is empty.

        Content is not loaded -- a listing is metadata, and pulling every rendered document to show
        a table of twenty rows would be wasteful for no benefit.
        """
        # `length(content)` rather than the column itself: the size is the one thing a listing needs
        # from the body, and measuring it in SQL keeps the document on the database side.
        query = "SELECT *, length(content) AS content_bytes FROM reports"
        params: tuple[Any, ...] = ()
        if scan_id:
            query += " WHERE scan_id = ?"
            params = (scan_id,)
        query += " ORDER BY generated_at DESC, id"

        async with self.database.connect() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
        return [_to_record(row, include_content=False) for row in rows]

    async def load_report(self, report_id: str) -> ReportRecord | None:
        """One report, content included."""
        async with self.database.connect() as conn:
            cursor = await conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
            row = await cursor.fetchone()
        return _to_record(row) if row else None

    async def delete_report(self, report_id: str) -> bool:
        """Delete a report and its export history.

        Returns whether anything was deleted, so a caller can distinguish "removed" from "was never
        there" -- reporting success for a no-op would hide a wrong id.
        """
        async with self.database.connect() as conn:
            cursor = await conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
            deleted = cursor.rowcount > 0
            await conn.execute("DELETE FROM report_exports WHERE report_id = ?", (report_id,))
            await conn.commit()

        if deleted:
            log.info("report deleted", extra={"report_id": report_id})
        return deleted

    async def record_export(
        self,
        report_id: str,
        fmt: str,
        path: str,
        *,
        scan_id: str = "",
        size_bytes: int = 0,
    ) -> None:
        """Append to the export log. Never updates -- history is append-only."""
        async with self.database.connect() as conn:
            await conn.execute(
                _INSERT_EXPORT,
                (
                    uuid.uuid4().hex,
                    report_id,
                    scan_id,
                    fmt,
                    path,
                    size_bytes,
                    datetime.now(UTC).isoformat(),
                ),
            )
            await conn.commit()

    async def exports_for(self, report_id: str) -> list[dict[str, Any]]:
        async with self.database.connect() as conn:
            cursor = await conn.execute(
                "SELECT * FROM report_exports WHERE report_id = ? ORDER BY exported_at",
                (report_id,),
            )
            rows = await cursor.fetchall()
        return [
            {
                "id": str(row["id"]),
                "report_id": str(row["report_id"]),
                "format": str(row["format"]),
                "path": str(row["path"]),
                "size_bytes": int(row["size_bytes"]),
                "exported_at": str(row["exported_at"]),
            }
            for row in rows
        ]

    async def count(self, scan_id: str = "") -> int:
        query = "SELECT COUNT(*) AS n FROM reports"
        params: tuple[Any, ...] = ()
        if scan_id:
            query += " WHERE scan_id = ?"
            params = (scan_id,)
        async with self.database.connect() as conn:
            cursor = await conn.execute(query, params)
            row = await cursor.fetchone()
        return int(row["n"]) if row else 0


def _to_record(row: Any, *, include_content: bool = True) -> ReportRecord:
    return ReportRecord(
        id=str(row["id"]),
        scan_id=str(row["scan_id"]),
        title=str(row["title"]),
        target=str(row["target"]),
        fmt=str(row["format"]),
        content=str(row["content"]) if include_content else "",
        stored_bytes=None if include_content else _optional_int(row, "content_bytes"),
        summary=_json(row["summary"], {}),
        finding_count=int(row["finding_count"]),
        risk_score=float(row["risk_score"]),
        status=str(row["status"]),
        report_version=str(row["report_version"]),
        analyzer_version=str(row["analyzer_version"]),
        framework_version=str(row["framework_version"]),
        generated_at=_timestamp(row["generated_at"]),
    )


def _optional_int(row: Any, column: str) -> int | None:
    """Read *column* as an int, or ``None`` when the query did not select it.

    ``load_report`` uses ``SELECT *`` and so has no ``content_bytes``; indexing a missing column on
    an ``aiosqlite.Row`` raises rather than returning ``None``.
    """
    try:
        value = row[column]
    except (IndexError, KeyError):
        return None
    return int(value) if value is not None else None


def _json(value: Any, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _timestamp(value: Any) -> datetime:
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return datetime.now(UTC)


__all__ = ["ReportRecord", "ReportRepository"]
