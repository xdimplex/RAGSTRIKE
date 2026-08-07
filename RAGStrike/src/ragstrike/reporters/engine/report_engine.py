"""``ReportEngine`` and ``ReportRegistry`` -- the unified interface, and format discovery.

**The Open/Closed requirement, concretely.** A new format is a class plus a `register()` call.
Nothing in this module names HTML, JSON, or Markdown; it asks the registry for whatever was
registered. Adding PDF later changes no code here.

**One interface regardless of format.** `generate()` returns a model, `render()` turns it into a
string, `export()` writes it. A caller switching from Markdown to HTML changes one argument.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
from typing import Any

from ragstrike.analyzers.base.finding import Finding
from ragstrike.core.errors import RAGStrikeError
from ragstrike.reporters.base.renderer import BaseRenderer
from ragstrike.reporters.builders.report_builder import ReportBuilder, ReportContext
from ragstrike.reporters.models.report import ReportModel
from ragstrike.reporters.validators.report_validator import (
    ReportValidation,
    ReportValidator,
)

log = logging.getLogger(__name__)

#: Bumped when the report structure changes in a way a consumer would notice. Recorded on every
#: report, because a stored report is only interpretable against the shape that produced it.
REPORT_VERSION = "1.0.0"


class UnknownFormatError(RAGStrikeError):
    """A format nobody registered."""

    code = "unknown_report_format"


class ReportRegistry:
    """Holds renderers and resolves one by name."""

    def __init__(self) -> None:
        self._renderers: dict[str, BaseRenderer] = {}

    def register(self, renderer: BaseRenderer, *, replace: bool = False) -> BaseRenderer:
        """Add *renderer* under its ``name``.

        Refuses a duplicate unless *replace* is set. Silently overwriting would make "which
        renderer produced this" depend on import order, and the symptom would be a subtly wrong
        report rather than an error anyone notices.
        """
        if not renderer.name:
            raise ValueError("renderer must declare a non-empty name")
        if renderer.name in self._renderers and not replace:
            raise ValueError(
                f"renderer {renderer.name!r} is already registered; "
                "pass replace=True to override deliberately"
            )
        self._renderers[renderer.name] = renderer
        log.debug("renderer registered", extra={"name": renderer.name})
        return renderer

    def get(self, name: str) -> BaseRenderer:
        renderer = self._renderers.get(name)
        if renderer is None:
            raise UnknownFormatError(
                f"No renderer registered for format {name!r}.",
                hint=f"Available: {', '.join(sorted(self._renderers)) or 'none'}.",
            )
        return renderer

    def names(self) -> list[str]:
        return sorted(self._renderers)

    def available(self) -> list[str]:
        """Formats that can actually render. Excludes declared placeholders."""
        return sorted(n for n, r in self._renderers.items() if r.implemented)

    def unregister(self, name: str) -> None:
        self._renderers.pop(name, None)

    def __len__(self) -> int:
        return len(self._renderers)

    def __contains__(self, name: object) -> bool:
        return name in self._renderers


@dataclass(frozen=True, slots=True)
class GeneratedReport:
    """A built report and the validation that let it through.

    Warnings travel with the report rather than being logged and forgotten: an operator reading a
    report built from findings with missing categories deserves to know that, and a log line they
    never see does not tell them.
    """

    model: ReportModel
    validation: ReportValidation = field(default_factory=ReportValidation)

    @property
    def report_id(self) -> str:
        return self.model.report_id

    @property
    def scan_id(self) -> str:
        return self.model.scan_id


class ReportEngine:
    """Builds report models and renders them. The unified interface."""

    def __init__(
        self,
        *,
        registry: ReportRegistry | None = None,
        builder: ReportBuilder | None = None,
        validator: ReportValidator | None = None,
    ) -> None:
        self.registry = registry or default_registry()
        self.builder = builder or ReportBuilder()
        self.validator = validator or ReportValidator()

    # -- generation ------------------------------------------------------------------------------

    def generate(
        self,
        findings: list[Finding],
        context: ReportContext | None = None,
        *,
        strict: bool = True,
    ) -> GeneratedReport:
        """Build a report model from *findings*.

        Args:
            findings: What the analyzer produced.
            context: Scan, target, and branding metadata.
            strict: Raise on validation errors. Left true -- a report built from incoherent input
                looks exactly as authoritative as a correct one, which is what makes accepting it
                dangerous.
        """
        resolved = context or ReportContext()
        validation = self.validator.validate_findings(findings)
        if strict:
            validation.raise_if_invalid()

        model = self.builder.build(findings, resolved)

        model_validation = self.validator.validate_model(model)
        if strict:
            model_validation.raise_if_invalid()

        combined = ReportValidation(
            errors=validation.errors + model_validation.errors,
            warnings=validation.warnings + model_validation.warnings,
        )
        if combined.warnings:
            log.info(
                "report generated with warnings",
                extra={"scan_id": model.scan_id, "warnings": len(combined.warnings)},
            )
        return GeneratedReport(model=model, validation=combined)

    # -- rendering -------------------------------------------------------------------------------

    def render(self, report: ReportModel | GeneratedReport, fmt: str) -> str:
        """Render *report* in *fmt*. One call regardless of format."""
        model = report.model if isinstance(report, GeneratedReport) else report
        return self.registry.get(fmt).render(model)

    def render_bytes(self, report: ReportModel | GeneratedReport, fmt: str) -> bytes:
        """Render *report* in *fmt* as bytes.

        Text renderers inherit a default that encodes :meth:`render`, so a caller writing files can
        use this one method for every format and never branch on which kind it got.
        """
        model = report.model if isinstance(report, GeneratedReport) else report
        return self.registry.get(fmt).render_bytes(model)

    def is_binary(self, fmt: str) -> bool:
        """Whether *fmt* produces bytes that must not be round-tripped through ``str``."""
        return bool(getattr(self.registry.get(fmt), "binary", False))

    def render_all(
        self, report: ReportModel | GeneratedReport, formats: list[str] | None = None
    ) -> dict[str, str]:
        """Render several formats at once.

        Defaults to every *available* format, skipping declared placeholders -- asking for
        "everything" should not fail because PDF is not implemented yet.
        """
        model = report.model if isinstance(report, GeneratedReport) else report
        chosen = formats or self.registry.available()
        return {fmt: self.registry.get(fmt).render(model) for fmt in chosen}

    def formats(self) -> dict[str, bool]:
        """Every registered format, mapped to whether it can actually render."""
        return {name: self.registry.get(name).implemented for name in self.registry.names()}

    def filename_for(self, report: ReportModel | GeneratedReport, fmt: str) -> str:
        model = report.model if isinstance(report, GeneratedReport) else report
        return self.registry.get(fmt).filename(model)


def default_registry() -> ReportRegistry:
    """A registry with the shipped renderers.

    Imported here rather than at module scope so the registry has no import-time dependency on any
    particular format -- which is what lets a caller build a registry containing only their own.
    """
    # Deferred deliberately. Importing these at module scope would make this module depend on
    # every shipped format, which is exactly the coupling the registry exists to remove -- a caller
    # building a registry of only their own renderers would still drag all four in.
    from ragstrike.reporters.html.renderer import HtmlRenderer  # noqa: PLC0415
    from ragstrike.reporters.json.renderer import JsonRenderer  # noqa: PLC0415
    from ragstrike.reporters.markdown.renderer import MarkdownRenderer  # noqa: PLC0415
    from ragstrike.reporters.pdf.renderer import PdfRenderer  # noqa: PLC0415

    registry = ReportRegistry()
    registry.register(HtmlRenderer())
    registry.register(JsonRenderer())
    registry.register(MarkdownRenderer())
    registry.register(PdfRenderer())
    return registry


def context_from(
    *,
    scan_id: str = "",
    target: str = "",
    findings: list[Finding] | None = None,
    **overrides: Any,
) -> ReportContext:
    """Build a :class:`ReportContext`, inferring what it can from *findings*.

    Convenience for the common case where scan id, analyzer version, and duration are all already
    present on the findings and repeating them by hand invites them to drift apart.
    """
    supplied = findings or []
    inferred: dict[str, Any] = {
        "scan_id": scan_id or (supplied[0].scan_id if supplied else ""),
        "target": target or str(supplied[0].metadata.get("target", "")) if supplied else target,
        "analyzer_version": supplied[0].analyzer_version if supplied else "",
        "report_version": REPORT_VERSION,
        "generated_at": datetime.now(UTC),
    }
    inferred.update({k: v for k, v in overrides.items() if v is not None})
    return ReportContext(**inferred)


__all__ = [
    "REPORT_VERSION",
    "GeneratedReport",
    "ReportEngine",
    "ReportRegistry",
    "UnknownFormatError",
    "context_from",
    "default_registry",
]
