"""``ragstrike.reporters`` -- the Reporting Engine.

Transforms the standardized ``Finding`` objects the Analyzer Engine produces into professional
security reports. It never talks to a plugin, and it never renders a UI.

One model, N renderers: every computation happens in the builders, and a renderer only chooses how
to present what it is given. Adding a format is a class plus a registration -- no existing code
changes.
"""

from ragstrike.reporters.base.renderer import BaseRenderer, ReportRepository
from ragstrike.reporters.builders.report_builder import ReportBuilder, ReportContext
from ragstrike.reporters.engine.report_engine import (
    REPORT_VERSION,
    GeneratedReport,
    ReportEngine,
    ReportRegistry,
    context_from,
    default_registry,
)
from ragstrike.reporters.exporters.export_manager import ExportManager, ExportRecord
from ragstrike.reporters.models.report import ReportModel
from ragstrike.reporters.validators.report_validator import ReportValidator

__all__ = [
    "REPORT_VERSION",
    "BaseRenderer",
    "ExportManager",
    "ExportRecord",
    "GeneratedReport",
    "ReportBuilder",
    "ReportContext",
    "ReportEngine",
    "ReportModel",
    "ReportRegistry",
    "ReportRepository",
    "ReportValidator",
    "context_from",
    "default_registry",
]
