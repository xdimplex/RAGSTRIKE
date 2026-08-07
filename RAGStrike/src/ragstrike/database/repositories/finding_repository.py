"""Persistence for analyzer findings.

**This module implements a port the analyzer defines.** ``ragstrike.analyzers`` sits below
``ragstrike.database`` in the layer contract, so the engine cannot import a repository -- and that
direction is deliberate. Analysis is a pure transformation; making it depend on SQLite would mean
the whole engine could only be exercised with a database attached.

So the dependency points this way instead: ``database`` imports ``analyzers`` to satisfy
:class:`~ragstrike.analyzers.base.ports.FindingRepository`. ``lint-imports`` enforces that the
reverse never happens.

Findings are stored separately from ``plugin_results`` on purpose. A plugin result records what was
*observed*; a finding records what the analyzer *concluded* from it, against a versioned rule set.
Re-running analysis after a rule change produces new findings over the same observations without
rewriting the record of what actually happened.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from typing import Any

from ragstrike.analyzers.base.finding import Finding
from ragstrike.database.connection import Database
from ragstrike.models.values.enums import PluginOutcome, Severity

log = logging.getLogger(__name__)

_INSERT = """
INSERT INTO findings (
    id, scan_id, plugin_id, category, status, severity, confidence, confidence_band,
    risk_score, evidence, recommendation, references_json, notes, analyzer_version,
    metadata, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class FindingRepository:
    """Reads and writes analyzer findings."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def add_findings(self, findings: list[Finding]) -> None:
        """Store *findings* in one transaction.

        Batched rather than per-finding so a scan's analysis lands atomically: a partially written
        analysis would be indistinguishable from one that found fewer problems.
        """
        if not findings:
            return

        rows = [
            (
                finding.id,
                finding.scan_id,
                finding.plugin_id,
                finding.category,
                finding.status.value,
                finding.severity.value,
                float(finding.confidence),
                finding.confidence_band,
                float(finding.risk_score),
                json.dumps(finding.evidence, default=str),
                finding.recommendation,
                json.dumps(list(finding.references)),
                finding.notes,
                finding.analyzer_version,
                json.dumps(finding.metadata, default=str),
                finding.timestamp.isoformat(),
            )
            for finding in findings
        ]

        async with self.database.connect() as conn:
            await conn.executemany(_INSERT, rows)
            await conn.commit()

        log.info(
            "findings stored",
            extra={"count": len(findings), "scan_id": findings[0].scan_id},
        )

    async def findings_for(self, scan_id: str) -> list[Finding]:
        """Every finding recorded for *scan_id*, oldest first."""
        async with self.database.connect() as conn:
            cursor = await conn.execute(
                "SELECT * FROM findings WHERE scan_id = ? ORDER BY created_at, id",
                (scan_id,),
            )
            rows = await cursor.fetchall()
        return [_to_finding(row) for row in rows]

    async def vulnerabilities_for(self, scan_id: str) -> list[Finding]:
        """Findings that assert a weakness.

        ``FAIL`` only. ``INCONCLUSIVE`` is excluded because an undetermined result is not evidence
        of weakness any more than of strength.
        """
        async with self.database.connect() as conn:
            cursor = await conn.execute(
                "SELECT * FROM findings WHERE scan_id = ? AND status = ? ORDER BY risk_score DESC",
                (scan_id, PluginOutcome.FAIL.value),
            )
            rows = await cursor.fetchall()
        return [_to_finding(row) for row in rows]

    async def count_for(self, scan_id: str) -> dict[str, int]:
        """Findings per status for *scan_id*.

        Every status appears, including zeros -- a missing key forces every caller to write
        ``.get(status, 0)``, and one that forgets renders a blank where a zero belongs.
        """
        counts = {outcome.value: 0 for outcome in PluginOutcome}
        async with self.database.connect() as conn:
            cursor = await conn.execute(
                "SELECT status, COUNT(*) AS n FROM findings WHERE scan_id = ? GROUP BY status",
                (scan_id,),
            )
            for row in await cursor.fetchall():
                counts[str(row["status"])] = int(row["n"])
        return counts


def _to_finding(row: Any) -> Finding:
    """Rebuild a Finding from a stored row.

    Unknown enum values fall back rather than raising: a database written by a newer version should
    still be readable, and a row nobody can load is worse than one whose severity reads INFO.
    """
    return Finding(
        id=str(row["id"]),
        scan_id=str(row["scan_id"]),
        plugin_id=str(row["plugin_id"]),
        category=str(row["category"]),
        status=_enum(PluginOutcome, row["status"], PluginOutcome.INCONCLUSIVE),
        severity=_enum(Severity, row["severity"], Severity.INFO),
        confidence=float(row["confidence"]),
        confidence_band=str(row["confidence_band"]),
        risk_score=float(row["risk_score"]),
        evidence=_json(row["evidence"], {}),
        recommendation=str(row["recommendation"]),
        references=tuple(_json(row["references_json"], [])),
        timestamp=_timestamp(row["created_at"]),
        notes=str(row["notes"]),
        analyzer_version=str(row["analyzer_version"]),
        metadata=_json(row["metadata"], {}),
    )


def _enum(enum_cls: Any, value: Any, fallback: Any) -> Any:
    try:
        return enum_cls(str(value))
    except ValueError:
        log.warning(
            "unknown enum value in findings row",
            extra={"enum": enum_cls.__name__, "value": str(value)},
        )
        return fallback


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


__all__ = ["FindingRepository"]
