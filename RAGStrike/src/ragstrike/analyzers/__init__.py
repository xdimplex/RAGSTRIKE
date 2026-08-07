"""``ragstrike.analyzers`` -- the Analyzer Engine.

Converts raw plugin execution results into standardized security findings. The engine is the only
component that decides a final security assessment: a plugin reports what it observed, and the
analyzer decides what that means using configurable rules.

Nothing here imports a plugin, a pack, or the database. Input is
:class:`~ragstrike.analyzers.base.observation.Observation`, derived from a domain entity, and
persistence is a port the caller supplies -- which is why the whole engine is testable offline.
"""

from ragstrike.analyzers.base import BaseAnalyzer, Finding, FindingRepository, Observation
from ragstrike.analyzers.engine import (
    ANALYZER_VERSION,
    AnalysisReport,
    AnalyzerEngine,
    StandardAnalyzer,
)

__all__ = [
    "ANALYZER_VERSION",
    "AnalysisReport",
    "AnalyzerEngine",
    "BaseAnalyzer",
    "Finding",
    "FindingRepository",
    "Observation",
    "StandardAnalyzer",
]
