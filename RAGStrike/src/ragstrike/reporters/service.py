"""``ReportService`` -- the internal API the future Dashboard calls.

Five operations: **generate, list, load, delete, export.** A caller uses these without knowing that
renderers exist, that a registry resolves them, or that reports live in SQLite. Swapping any of that
changes nothing on this surface, which is the point of having one.

**The repository arrives as a parameter, not an import.** ``reporters`` sits below ``database`` in
the layer contract, so the service takes a :class:`~ragstrike.reporters.base.renderer.ReportRepository`
and the database layer supplies one. Report generation stays testable with no database attached.

**Persisting is separate from generating.** ``generate()`` returns a model and touches nothing;
``store()`` writes. A caller previewing a report should not have to clean up after itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ragstrike.analyzers.base.finding import Finding
from ragstrike.reporters.base.record import StoredReport
from ragstrike.reporters.builders.report_builder import ReportContext
from ragstrike.reporters.engine.report_engine import (
    REPORT_VERSION,
    GeneratedReport,
    ReportEngine,
)
from ragstrike.reporters.exporters.export_manager import ExportManager, ExportRecord
from ragstrike.reporters.models.report import ReportModel


@dataclass(frozen=True, slots=True)
class ReportSummary:
    """What a listing returns. Metadata only -- never the rendered document."""

    report_id: str
    scan_id: str
    title: str
    target: str
    status: str
    risk_score: float
    finding_count: int
    generated_at: str
    fmt: str = "json"

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "scan_id": self.scan_id,
            "title": self.title,
            "target": self.target,
            "status": self.status,
            "risk_score": round(self.risk_score, 2),
            "finding_count": self.finding_count,
            "generated_at": self.generated_at,
            "format": self.fmt,
        }


class ReportService:
    """The unified reporting interface."""

    def __init__(
        self,
        *,
        engine: ReportEngine | None = None,
        repository: Any = None,
        output_dir: Path | None = None,
    ) -> None:
        self.engine = engine or ReportEngine()
        #: A ``ReportRepository``. Typed loosely because naming the protocol here would not change
        #: what is accepted at runtime, and the port is the documented contract.
        self.repository = repository
        self.exports = ExportManager(self.engine, output_dir)

    # -- generate ---------------------------------------------------------------------------------

    def generate(
        self,
        findings: list[Finding],
        context: ReportContext | None = None,
        *,
        strict: bool = True,
    ) -> GeneratedReport:
        """Build a report. Touches no storage and no filesystem."""
        return self.engine.generate(findings, context, strict=strict)

    def render(self, report: ReportModel | GeneratedReport, fmt: str = "html") -> str:
        """Render in *fmt*. Same call regardless of format."""
        return self.engine.render(report, fmt)

    def formats(self) -> dict[str, bool]:
        """Every known format, mapped to whether it can actually render."""
        return self.engine.formats()

    # -- persist ----------------------------------------------------------------------------------

    async def store(self, report: GeneratedReport | ReportModel, *, fmt: str = "json") -> str:
        """Render and persist, returning the report id.

        The rendered content is stored alongside the metadata. Regenerating later would produce a
        different document the moment a template changed, and a stored report is meant to be the
        record of what was actually shown.
        """
        self._require_repository()
        model = report.model if isinstance(report, GeneratedReport) else report

        record = StoredReport(
            id=model.report_id,
            scan_id=model.scan_id,
            title=model.cover.title,
            target=model.cover.target,
            fmt=fmt,
            content=self.engine.render(model, fmt),
            summary=model.summary.to_dict(),
            finding_count=len(model.findings),
            risk_score=model.summary.risk_score,
            status=model.summary.status,
            report_version=model.cover.report_version or REPORT_VERSION,
            analyzer_version=model.cover.analyzer_version,
            framework_version=model.cover.framework_version,
            generated_at=model.cover.generated_at,
        )
        await self.repository.save_report(record)
        return record.id

    async def list_reports(self, scan_id: str = "") -> list[ReportSummary]:
        """Stored reports, newest first."""
        self._require_repository()
        records = await self.repository.list_reports(scan_id)
        return [
            ReportSummary(
                report_id=r.id,
                scan_id=r.scan_id,
                title=r.title,
                target=r.target,
                status=r.status,
                risk_score=r.risk_score,
                finding_count=r.finding_count,
                generated_at=r.generated_at.isoformat(),
                fmt=r.fmt,
            )
            for r in records
        ]

    async def load_report(self, report_id: str) -> str | None:
        """The stored rendered content, or ``None`` when there is no such report."""
        self._require_repository()
        record = await self.repository.load_report(report_id)
        return record.content if record else None

    async def delete_report(self, report_id: str) -> bool:
        """Delete a report. Returns whether anything was removed."""
        self._require_repository()
        return bool(await self.repository.delete_report(report_id))

    # -- export -----------------------------------------------------------------------------------

    async def export(
        self,
        report: GeneratedReport | ReportModel,
        fmt: str = "html",
        *,
        output_dir: Path | None = None,
    ) -> ExportRecord:
        """Write a rendered report to disk, recording the export when a repository is attached.

        Works without one: exporting to a file is useful in a CI job that has no database, and
        requiring storage for it would make the simplest case the hardest.
        """
        record = self.exports.export(report, fmt, output_dir=output_dir)
        if self.repository is not None:
            await self.repository.record_export(
                record.report_id,
                record.fmt,
                str(record.path),
                scan_id=record.scan_id,
                size_bytes=record.size_bytes,
            )
        return record

    # -- internals --------------------------------------------------------------------------------

    def _require_repository(self) -> None:
        if self.repository is None:
            raise ValueError(
                "This operation needs a repository. Construct ReportService(repository=...) "
                "with a ReportRepository, or use generate/render/export, which do not persist."
            )


__all__ = ["ReportService", "ReportSummary"]
