"""``ExportManager`` -- writing rendered reports to disk.

The one component here that performs I/O. Kept apart from rendering so that generating a report and
persisting one are separately testable: every renderer returns a string, and only this writes.

**Filenames are derived, never taken from input.** A scan id reaches this layer from configuration
and from a database, and a report written to `../../etc/something` because an id contained path
separators would be a directory traversal in a security tool. Every component is sanitized.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
from pathlib import Path
import re
from typing import Any

from ragstrike.core.errors import RAGStrikeError
from ragstrike.reporters.engine.report_engine import GeneratedReport, ReportEngine
from ragstrike.reporters.models.report import ReportModel

log = logging.getLogger(__name__)

#: Anything outside this is replaced. Deliberately strict -- a filename is not a place to preserve
#: interesting characters.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


class ExportError(RAGStrikeError):
    """A report could not be written."""

    code = "report_export_error"


def safe_component(value: str, *, fallback: str = "report") -> str:
    """Reduce *value* to something safe to put in a filename.

    Strips directory separators, parent references, and anything unusual. Returns *fallback* when
    nothing usable survives, because an empty filename component produces a path nobody intended.
    """
    cleaned = _UNSAFE.sub("-", value).strip("-.")
    return cleaned or fallback


@dataclass(frozen=True, slots=True)
class ExportRecord:
    """One written file."""

    report_id: str
    scan_id: str
    fmt: str
    path: Path
    size_bytes: int
    exported_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "scan_id": self.scan_id,
            "format": self.fmt,
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "exported_at": self.exported_at.isoformat(),
        }


class ExportManager:
    """Renders and writes reports."""

    def __init__(self, engine: ReportEngine, output_dir: Path | None = None) -> None:
        self.engine = engine
        self.output_dir = output_dir or Path("reports")

    def export(
        self,
        report: ReportModel | GeneratedReport,
        fmt: str,
        *,
        output_dir: Path | None = None,
        filename: str | None = None,
    ) -> ExportRecord:
        """Render *report* as *fmt* and write it.

        Creates the output directory if absent -- a report that fails because nobody made a folder
        first is a bad first experience for a tool that just spent minutes scanning.
        """
        model = report.model if isinstance(report, GeneratedReport) else report
        directory = output_dir or self.output_dir

        # Binary formats (PDF) must be written as bytes. Encoding a PDF to UTF-8 and back would
        # corrupt it silently -- producing a file with the right name and extension that no reader
        # can open, which is precisely the failure the placeholder era was designed to avoid.
        payload = self.engine.render_bytes(model, fmt)
        name = safe_component(
            filename or self.engine.filename_for(model, fmt), fallback=f"report.{fmt}"
        )
        path = directory / name

        try:
            directory.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        except OSError as exc:
            raise ExportError(
                f"Could not write {path}: {exc}",
                hint="Check the directory exists and is writable.",
            ) from exc

        record = ExportRecord(
            report_id=model.report_id,
            scan_id=model.scan_id,
            fmt=fmt,
            path=path,
            size_bytes=len(payload),
        )
        log.info(
            "report exported",
            extra={"format": fmt, "path": str(path), "bytes": record.size_bytes},
        )
        return record

    def export_all(
        self,
        report: ReportModel | GeneratedReport,
        formats: list[str] | None = None,
        *,
        output_dir: Path | None = None,
    ) -> list[ExportRecord]:
        """Export several formats.

        Defaults to every *available* format, skipping declared placeholders -- asking for
        "everything" should not fail because PDF is not implemented yet.
        """
        chosen = formats or self.engine.registry.available()
        return [self.export(report, fmt, output_dir=output_dir) for fmt in chosen]


__all__ = ["ExportError", "ExportManager", "ExportRecord", "safe_component"]
