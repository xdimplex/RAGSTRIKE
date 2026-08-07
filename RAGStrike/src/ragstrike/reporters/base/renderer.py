"""``BaseRenderer`` -- the contract every output format implements, and the ports reporting needs.

**One interface regardless of format.** A caller asks for HTML, JSON, or Markdown through the same
method and gets a string back. Adding a format means adding a class and registering it; no existing
code changes, which is the Open/Closed requirement made concrete.

**Binary formats declare themselves.** PDF cannot round-trip through ``str``, so a renderer may set
``binary = True`` and implement :meth:`render_bytes`; the exporter then writes bytes instead of
encoding text. ``render`` still exists for such a renderer and returns a short human-readable note,
so nothing that calls the text path gets a stack trace or, worse, a mojibake file.

**A renderer presents; it never calculates.** Every number reaching a renderer was computed once by
the builders. A renderer that recomputed anything would let two formats disagree about the same
scan, and the disagreement would surface as a support question rather than a test failure.
"""

from __future__ import annotations

import abc
from typing import Protocol, runtime_checkable

from ragstrike.reporters.models.report import ReportModel


class BaseRenderer(abc.ABC):
    """Turns a :class:`ReportModel` into text in one format."""

    #: Registry key and the name a caller asks for. Must be unique.
    name: str = ""

    #: File extension for exports, without the dot.
    extension: str = "txt"

    #: MIME type, for a future HTTP surface.
    media_type: str = "text/plain"

    #: False for a format that is declared but not implemented. The engine refuses to render one
    #: rather than emitting a plausible-looking empty file.
    implemented: bool = True

    #: True when the real output is bytes rather than text. Exporters check this before writing.
    binary: bool = False

    @abc.abstractmethod
    def render(self, report: ReportModel) -> str:
        """Render *report*. Must be pure: same model in, same bytes out."""

    def render_bytes(self, report: ReportModel) -> bytes:
        """Binary output for a renderer that has any.

        The default encodes :meth:`render`, so every text renderer satisfies this without knowing it
        exists and an exporter can use one code path for both.
        """
        return self.render(report).encode("utf-8")

    def filename(self, report: ReportModel) -> str:
        """Default export filename. Uses the scan id rather than the report id because that is what
        an operator recognises when looking through a directory."""
        stem = report.scan_id or report.report_id
        return f"ragstrike-{stem}.{self.extension}"


@runtime_checkable
class Renderer(Protocol):
    """What the registry accepts.

    Narrower than :class:`BaseRenderer` so a third party can satisfy it without inheriting from
    anything of ours.
    """

    name: str
    extension: str

    def render(self, report: ReportModel) -> str: ...


@runtime_checkable
class ReportRepository(Protocol):
    """Persistence for report metadata and export history.

    A port for the same reason the analyzer has one: ``reporters`` sits below ``database`` in the
    layer contract, so the engine declares what it needs and the database layer implements it.
    Report generation stays a pure transformation, testable with no database attached.
    """

    async def save_report(self, record: object) -> None: ...

    async def list_reports(self, scan_id: str = "") -> list[object]: ...

    async def load_report(self, report_id: str) -> object | None: ...

    async def delete_report(self, report_id: str) -> bool: ...

    async def record_export(self, report_id: str, fmt: str, path: str) -> None: ...


__all__ = ["BaseRenderer", "Renderer", "ReportRepository"]
