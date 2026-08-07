"""``StoredReport`` -- the payload crossing the persistence port.

**This type exists so ``reporters`` never imports ``database``.** The first attempt had
``ReportService.store()`` build the repository's own record type, deferred inside the function to
dodge a module-level import. ``lint-imports`` caught it anyway -- grimp reads the whole AST, so a
function-level import is still an import -- and it was right to: a deferred import is the same
dependency, just harder to see.

So the shape is defined here, on the lower layer, and the database maps it onto a row. The
dependency points the way the contract requires, and report generation stays testable with no
database attached.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class StoredReport:
    """A rendered report and its metadata, ready to persist.

    ``content`` is the rendered document, stored rather than regenerated. A report is an artifact
    someone made a decision from; rebuilding it later would produce a different document the moment
    a template or renderer changed, and "what did the report actually say in March" is exactly what
    an audit asks.
    """

    id: str
    scan_id: str
    title: str = ""
    target: str = ""
    fmt: str = "json"
    content: str = ""
    summary: dict[str, Any] = field(default_factory=dict)
    finding_count: int = 0
    risk_score: float = 0.0
    status: str = ""
    report_version: str = ""
    analyzer_version: str = ""
    framework_version: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    #: Size recorded by a metadata-only load, where ``content`` was deliberately not fetched.
    #: ``None`` means "measure the content I am holding".
    stored_bytes: int | None = None

    @property
    def size_bytes(self) -> int:
        """How large the rendered document is.

        A listing loads metadata WITHOUT ``content`` on purpose, so measuring the (empty) content
        there reported every stored report as 0 bytes -- a plausible-looking number that was simply
        false. When the loader knows the real size it passes ``stored_bytes`` and that wins.
        """
        if self.stored_bytes is not None:
            return self.stored_bytes
        return len(self.content.encode("utf-8"))

    def to_dict(self) -> dict[str, Any]:
        """Metadata only -- ``content`` is excluded deliberately.

        A listing of twenty reports would otherwise carry twenty rendered documents. Callers that
        want the content ask for one report by id.
        """
        return {
            "id": self.id,
            "scan_id": self.scan_id,
            "title": self.title,
            "target": self.target,
            "format": self.fmt,
            "summary": self.summary,
            "finding_count": self.finding_count,
            "risk_score": round(self.risk_score, 2),
            "status": self.status,
            "report_version": self.report_version,
            "analyzer_version": self.analyzer_version,
            "framework_version": self.framework_version,
            "generated_at": self.generated_at.isoformat(),
            "size_bytes": self.size_bytes,
        }


__all__ = ["StoredReport"]
