"""``RecommendationEngine`` -- retrieved advice, never generated.

**Advice is looked up, not written at analysis time (ADR-012).** A model composing remediation would
produce text that differs between identical runs and that nobody reviewed before it reached an
operator. Every string this returns was written once, by a person, and lives in a config file.

**Three scopes, most specific first:** plugin, then category, then severity. A pack that ships
precise advice for its own failure modes keeps it; anything unrecognised still gets something
useful rather than an empty field.

This does not replace the per-pack catalogs. A pack's own recommendation is carried on the
observation and preferred when present — the packs know their failure modes better than a
severity-keyed default ever could. This engine fills the gap for plugins that ship none, and gives
an operator one file to override all of them from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ragstrike.models.values.enums import Severity


@dataclass(frozen=True, slots=True)
class RecommendationEntry:
    """One piece of retrieved advice."""

    title: str
    remediation: str = ""
    references: tuple[str, ...] = ()
    effort: str = "MEDIUM"
    #: Which scope supplied it -- ``plugin`` / ``category`` / ``severity`` / ``default``. Recorded
    #: so an operator can see why they got this advice and where to override it.
    scope: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "remediation": self.remediation,
            "references": list(self.references),
            "effort": self.effort,
            "scope": self.scope,
        }


@dataclass(frozen=True, slots=True)
class RecommendationCatalog:
    """Advice indexed by plugin, category, and severity."""

    by_plugin: dict[str, RecommendationEntry] = field(default_factory=dict)
    by_category: dict[str, RecommendationEntry] = field(default_factory=dict)
    by_severity: dict[str, RecommendationEntry] = field(default_factory=dict)
    default: RecommendationEntry | None = None
    #: Reserved. Future localization selects a catalog by locale; the field exists so that arrives
    #: without a shape change.
    locale: str = "en"

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> RecommendationCatalog:
        def parse(entries: Any, scope: str) -> dict[str, RecommendationEntry]:
            if not isinstance(entries, dict):
                return {}
            return {
                str(key): _entry(value, scope)
                for key, value in entries.items()
                if isinstance(value, dict)
            }

        default_raw = raw.get("default")
        return cls(
            by_plugin=parse(raw.get("by_plugin"), "plugin"),
            by_category=parse(raw.get("by_category"), "category"),
            by_severity={
                k.upper(): v for k, v in parse(raw.get("by_severity"), "severity").items()
            },
            default=_entry(default_raw, "default") if isinstance(default_raw, dict) else None,
            locale=str(raw.get("locale", "en")),
        )


def _entry(raw: dict[str, Any], scope: str) -> RecommendationEntry:
    return RecommendationEntry(
        title=str(raw.get("title", "")),
        remediation=str(raw.get("remediation", "")).strip(),
        references=tuple(str(r) for r in raw.get("references") or ()),
        effort=str(raw.get("effort", "MEDIUM")),
        scope=scope,
    )


class RecommendationEngine:
    """Looks up advice. Pure and stateless."""

    def __init__(self, catalog: RecommendationCatalog | None = None) -> None:
        self.catalog = catalog or RecommendationCatalog()

    def recommend(
        self,
        *,
        plugin_id: str,
        category: str,
        severity: Severity,
        plugin_supplied: str = "",
    ) -> RecommendationEntry:
        """Most specific advice available.

        Args:
            plugin_id: Checked first.
            category: Checked second.
            severity: Checked third.
            plugin_supplied: What the pack itself recommended. Preferred over every catalog entry
                when present, because a pack that shipped advice for its own failure modes knows
                more about them than a severity-keyed default. The catalog is the fallback and the
                override surface, not a replacement.
        """
        if plugin_supplied:
            return RecommendationEntry(title=plugin_supplied, scope="plugin-supplied")

        entry = self.catalog.by_plugin.get(plugin_id)
        if entry is not None:
            return entry

        entry = self.catalog.by_category.get(category)
        if entry is not None:
            return entry

        entry = self.catalog.by_severity.get(severity.value)
        if entry is not None:
            return entry

        return self.catalog.default or RecommendationEntry(
            title="Review this finding",
            remediation=(
                "No catalog entry matched this plugin, category, or severity. Add one in "
                "configs/analyzer/recommendations.yaml so future findings of this kind carry "
                "actionable advice."
            ),
            scope="default",
        )


def load_recommendation_catalog(path: Path) -> RecommendationCatalog:
    """Load from YAML or JSON, falling back to an empty catalog on any problem."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return RecommendationCatalog()
    return (
        RecommendationCatalog.from_mapping(raw)
        if isinstance(raw, dict)
        else RecommendationCatalog()
    )


__all__ = [
    "RecommendationCatalog",
    "RecommendationEngine",
    "RecommendationEntry",
    "load_recommendation_catalog",
]
