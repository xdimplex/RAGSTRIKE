"""Assembling an :class:`AnalyzerEngine` from ``configs/analyzer/``.

Separated from the engine so that constructing one in a test needs no filesystem and no config
tree. The engine's own defaults are usable on their own; this is the path that reads an operator's
tuning.

**A missing or malformed config file degrades, it does not abort.** Every loader falls back to
built-in defaults, and what was skipped is reported on :class:`AnalyzerConfigReport`. A security
tool that refuses to analyze because one YAML file has a typo is one that does not get run -- but a
tool that silently ignores the file an operator just edited is worse, so the fallbacks are recorded
rather than hidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ragstrike.analyzers.confidence.confidence_engine import (
    ConfidenceConfig,
    ConfidenceEngine,
    load_confidence_config,
)
from ragstrike.analyzers.engine import AnalyzerEngine, StandardAnalyzer
from ragstrike.analyzers.evidence.evidence_engine import EvidenceEngine
from ragstrike.analyzers.recommendations.recommendation_engine import (
    RecommendationEngine,
    load_recommendation_catalog,
)
from ragstrike.analyzers.registry.analyzer_registry import AnalyzerRegistry
from ragstrike.analyzers.rules.rule_engine import RuleEngine, load_ruleset
from ragstrike.analyzers.scoring.score_engine import ScoreEngine, load_scoring_config
from ragstrike.analyzers.validators.validation_engine import ValidationEngine

#: Where configuration lives, relative to the repository root.
DEFAULT_CONFIG_DIR = Path("configs") / "analyzer"


@dataclass(frozen=True, slots=True)
class AnalyzerConfigReport:
    """What was loaded, and what fell back to defaults.

    Returned alongside the engine so a caller can log or surface the difference. An operator who
    edited ``rules.yaml`` and got default grading anyway deserves to find out from a report rather
    than from a confusing scan result.
    """

    config_dir: Path
    loaded: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    skipped_rules: tuple[str, ...] = field(default_factory=tuple)
    rules_version: str = ""
    scoring_version: str = ""

    @property
    def fully_configured(self) -> bool:
        return not self.missing and not self.skipped_rules

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_dir": str(self.config_dir),
            "loaded": list(self.loaded),
            "missing": list(self.missing),
            "skipped_rules": list(self.skipped_rules),
            "rules_version": self.rules_version,
            "scoring_version": self.scoring_version,
        }


def _settings(config_dir: Path) -> dict[str, Any]:
    """Read ``analyzer.yaml``, which names the other files."""
    path = config_dir / "analyzer.yaml"
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}
    section = raw.get("analyzer")
    return section if isinstance(section, dict) else {}


def _resolve(config_dir: Path, value: Any, fallback: str) -> Path:
    """Resolve a configured path. Relative resolves against *config_dir*."""
    candidate = Path(str(value or fallback))
    return candidate if candidate.is_absolute() else config_dir / candidate


def build_engine(
    config_dir: Path | None = None,
    *,
    registry: AnalyzerRegistry | None = None,
) -> tuple[AnalyzerEngine, AnalyzerConfigReport]:
    """Build an engine from *config_dir*, with a report of what was actually loaded.

    Args:
        config_dir: Directory holding the five config files. Defaults to ``configs/analyzer``.
        registry: Registry to use. A fresh one is created when omitted, so building an engine never
            mutates process-wide state as a side effect.

    Returns:
        The engine and a report naming every file that was missing or fell back.
    """
    directory = config_dir or DEFAULT_CONFIG_DIR
    settings = _settings(directory)

    loaded: list[str] = []
    missing: list[str] = []

    def track(name: str, path: Path) -> Path:
        (loaded if path.is_file() else missing).append(name)
        return path

    rules_path = track("rules", _resolve(directory, settings.get("rules"), "rules.yaml"))
    scoring_path = track("scoring", _resolve(directory, settings.get("scoring"), "scoring.yaml"))
    confidence_path = track(
        "confidence", _resolve(directory, settings.get("confidence"), "confidence.yaml")
    )
    recommendations_path = track(
        "recommendations",
        _resolve(directory, settings.get("recommendations"), "recommendations.yaml"),
    )
    if not (directory / "analyzer.yaml").is_file():
        missing.append("analyzer")

    ruleset = load_ruleset(rules_path)
    scoring = load_scoring_config(scoring_path)
    confidence: ConfidenceConfig = load_confidence_config(confidence_path)
    catalog = load_recommendation_catalog(recommendations_path)

    scores = ScoreEngine(scoring)
    analyzer = StandardAnalyzer(
        rules=RuleEngine(ruleset),
        evidence=EvidenceEngine(),
        confidence=ConfidenceEngine(confidence),
        scores=scores,
        recommendations=RecommendationEngine(catalog),
    )

    engine = AnalyzerEngine(
        registry=registry or AnalyzerRegistry(),
        validator=ValidationEngine(),
        scores=scores,
        default_analyzer=analyzer,
    )

    report = AnalyzerConfigReport(
        config_dir=directory,
        loaded=tuple(loaded),
        missing=tuple(missing),
        skipped_rules=ruleset.skipped,
        rules_version=ruleset.version,
        scoring_version=scoring.model_version,
    )
    return engine, report


__all__ = ["DEFAULT_CONFIG_DIR", "AnalyzerConfigReport", "build_engine"]
