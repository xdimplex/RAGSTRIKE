"""The unified interface and format registry."""

from ragstrike.reporters.engine.report_engine import (
    REPORT_VERSION,
    GeneratedReport,
    ReportEngine,
    ReportRegistry,
    UnknownFormatError,
    context_from,
    default_registry,
)

__all__ = [
    "REPORT_VERSION",
    "GeneratedReport",
    "ReportEngine",
    "ReportRegistry",
    "UnknownFormatError",
    "context_from",
    "default_registry",
]
