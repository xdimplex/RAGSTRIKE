"""``RuleEngine`` -- configurable rules that decide status and severity.

**This is the component that makes the analyzer, rather than the plugin, the author of a finding.**
A plugin reports what it concluded; a rule here can agree, sharpen, or overrule it. Because rules
live in YAML, an operator re-grades every pack by editing a file -- no plugin change, no redeploy of
detection logic.

**Conditions are data, never code.** A rule declares field/operator/value triples that this module
interprets. Nothing is ``eval``'d, no expression is parsed, no attribute is traversed by name from
config. That is the same rule payloads follow (ADR-016): a rules file is untrusted input, and a
scanner whose configuration format is a code-execution surface is a bad trade.

**First match wins, by explicit priority.** Rules are sorted by descending priority and the first
match decides. Accumulating every match would make the outcome depend on file order in ways nobody
can predict from reading one rule.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ragstrike.analyzers.base.observation import Observation
from ragstrike.models.values.enums import PluginOutcome, Severity

#: Operators a condition may use. Closed set -- a rules file naming anything else is refused at
#: load time rather than silently never matching.
#:
#: Signature is ``(observed, expected) -> bool``. Both sides are ``Any``: the observed value comes
#: from the fact table and the expected one straight out of YAML, so neither is constrained.
_OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": lambda observed, expected: observed == expected,
    "ne": lambda observed, expected: observed != expected,
    "gt": lambda observed, expected: _num(observed) > _num(expected),
    "gte": lambda observed, expected: _num(observed) >= _num(expected),
    "lt": lambda observed, expected: _num(observed) < _num(expected),
    "lte": lambda observed, expected: _num(observed) <= _num(expected),
    "in": lambda observed, expected: (
        observed in expected if isinstance(expected, list | tuple | set) else False
    ),
    "not_in": lambda observed, expected: (
        observed not in expected if isinstance(expected, list | tuple | set) else True
    ),
    "contains": lambda observed, expected: str(expected).lower() in str(observed).lower(),
    "exists": lambda observed, expected: (observed is not None) is bool(expected),
}


def _num(value: Any) -> float:
    """Coerce to a number for comparison, treating anything uncoercible as zero.

    A rule comparing a missing field against a threshold should simply not match, rather than
    raising and taking down the analysis of an otherwise fine observation.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True, slots=True)
class Condition:
    """One field/operator/value test."""

    field: str
    operator: str
    value: Any = None

    def evaluate(self, facts: dict[str, Any]) -> bool:
        check = _OPERATORS.get(self.operator)
        if check is None:
            return False
        return bool(check(facts.get(self.field), self.value))

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "operator": self.operator, "value": self.value}


@dataclass(frozen=True, slots=True)
class Rule:
    """One rule: when every condition holds, apply these effects.

    Attributes:
        id: Unique identifier, recorded on the finding so a verdict traces to the rule that made it.
        description: Why this rule exists. Carried into the finding's notes.
        priority: Higher wins. Ties break on file order, which is why explicit priorities matter.
        applies_to: Categories this rule is scoped to. Empty means every category.
        conditions: All must hold -- AND. An OR is expressed as two rules, which reads better than
            nested boolean config.
        status: Status to assign when the rule matches. ``None`` leaves it to the next rule or the
            fallback.
        severity: Severity to assign.
        confidence_modifier: Added to the computed confidence, then clamped.
        stop: Whether matching ends evaluation. True by default -- first match wins.
    """

    id: str
    conditions: tuple[Condition, ...] = ()
    description: str = ""
    priority: int = 0
    applies_to: tuple[str, ...] = ()
    status: PluginOutcome | None = None
    severity: Severity | None = None
    confidence_modifier: float = 0.0
    stop: bool = True

    def matches(self, facts: dict[str, Any], category: str) -> bool:
        if self.applies_to and category not in self.applies_to:
            return False
        return all(condition.evaluate(facts) for condition in self.conditions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "priority": self.priority,
            "applies_to": list(self.applies_to),
            "conditions": [c.to_dict() for c in self.conditions],
            "status": self.status.value if self.status else None,
            "severity": self.severity.value if self.severity else None,
            "confidence_modifier": self.confidence_modifier,
        }


@dataclass(frozen=True, slots=True)
class RuleOutcome:
    """What the rule engine decided, and how."""

    status: PluginOutcome
    severity: Severity
    confidence_modifier: float = 0.0
    matched: tuple[str, ...] = ()
    notes: str = ""
    #: True when a rule assigned a status differing from what the plugin reported. Recorded because
    #: an operator reading a finding deserves to know the analyzer disagreed with the plugin.
    overrode_plugin: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "severity": self.severity.value,
            "confidence_modifier": self.confidence_modifier,
            "matched_rules": list(self.matched),
            "overrode_plugin": self.overrode_plugin,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class RuleSet:
    """Rules plus the fallback used when none match."""

    rules: tuple[Rule, ...] = ()
    default_severity: Severity = Severity.MEDIUM
    version: str = "1.0.0"
    skipped: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ordered(self) -> list[Rule]:
        """Descending priority. Stable, so equal priorities keep file order."""
        return sorted(self.rules, key=lambda r: -r.priority)


class RuleEngine:
    """Evaluates rules against observations. Pure and stateless."""

    def __init__(self, ruleset: RuleSet | None = None) -> None:
        self.ruleset = ruleset or RuleSet()

    # -- facts -------------------------------------------------------------------------------

    @staticmethod
    def facts_for(observation: Observation) -> dict[str, Any]:
        """The flat fact table a condition's ``field`` addresses.

        Flat and explicit rather than allowing dotted paths into arbitrary structures: a rules file
        that can traverse anything becomes coupled to every pack's internal evidence shape, and
        then no pack can change its evidence without breaking somebody's rules.
        """
        return {
            "plugin_id": observation.plugin_id,
            "category": observation.category,
            "reported_status": observation.reported_status.value,
            "reported_confidence": observation.reported_confidence,
            "execution_ms": observation.execution_ms,
            "payloads_executed": observation.payloads_executed,
            "total_cases": observation.total_cases,
            "failed_cases": observation.failed_cases,
            "failure_ratio": observation.failure_ratio,
            "has_error": bool(observation.error),
            "has_evidence": bool(observation.evidence),
            "target": observation.target,
        }

    # -- evaluation --------------------------------------------------------------------------

    def evaluate(self, observation: Observation) -> RuleOutcome:
        """Decide status and severity for *observation*.

        With no rule matching, the plugin's reported status stands and severity falls back to the
        ruleset default. That fallback is deliberate: an empty rules file must still produce usable
        findings, so the engine degrades to "trust the plugin" rather than to "no finding".
        """
        facts = self.facts_for(observation)
        status = observation.reported_status
        severity = self.ruleset.default_severity
        modifier = 0.0
        matched: list[str] = []
        notes: list[str] = []

        for rule in self.ruleset.ordered:
            if not rule.matches(facts, observation.category):
                continue

            matched.append(rule.id)
            if rule.description:
                notes.append(f"{rule.id}: {rule.description}")
            if rule.status is not None:
                status = rule.status
            if rule.severity is not None:
                severity = rule.severity
            modifier += rule.confidence_modifier
            if rule.stop:
                break

        overrode = status is not observation.reported_status
        if overrode:
            notes.append(
                f"analyzer status {status.value} overrides plugin-reported "
                f"{observation.reported_status.value}"
            )

        return RuleOutcome(
            status=status,
            severity=severity,
            confidence_modifier=modifier,
            matched=tuple(matched),
            notes="; ".join(notes),
            overrode_plugin=overrode,
        )


# -- loading -------------------------------------------------------------------------------------


def load_ruleset(path: Path) -> RuleSet:
    """Load rules from YAML or JSON.

    A malformed *rule* is skipped and named in :attr:`RuleSet.skipped` rather than raising: one bad
    rule should not disable grading entirely. A malformed *file* yields an empty ruleset, and the
    engine's fallback keeps producing findings from plugin-reported status.

    ``yaml.safe_load`` parses JSON too, so both formats the brief names are supported by one path.
    Database-backed rules would implement the same ``RuleSet`` construction, which is why loading
    is a free function rather than a method.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return RuleSet()
    if not isinstance(raw, dict):
        return RuleSet()

    rules: list[Rule] = []
    skipped: list[str] = []

    for entry in raw.get("rules") or []:
        if not isinstance(entry, dict) or not entry.get("id"):
            skipped.append(str(entry)[:60] if entry else "<empty>")
            continue
        try:
            rules.append(_parse_rule(entry))
        except (ValueError, KeyError, TypeError) as exc:
            skipped.append(f"{entry.get('id')}: {exc}")

    return RuleSet(
        rules=tuple(rules),
        default_severity=_severity(raw.get("default_severity"), Severity.MEDIUM),
        version=str(raw.get("version", "1.0.0")),
        skipped=tuple(skipped),
    )


def _parse_rule(entry: dict[str, Any]) -> Rule:
    conditions: list[Condition] = []
    for raw in entry.get("conditions") or []:
        if not isinstance(raw, dict):
            continue
        operator = str(raw.get("operator", "eq"))
        if operator not in _OPERATORS:
            # Refused rather than skipped silently: a rule with an unknown operator would never
            # match, and "never matches" is indistinguishable from "the target is fine".
            raise ValueError(f"unknown operator {operator!r}")
        conditions.append(
            Condition(field=str(raw.get("field", "")), operator=operator, value=raw.get("value"))
        )

    return Rule(
        id=str(entry["id"]),
        conditions=tuple(conditions),
        description=str(entry.get("description", "")),
        priority=int(entry.get("priority", 0)),
        applies_to=tuple(str(c) for c in entry.get("applies_to") or ()),
        status=_status(entry.get("status")),
        severity=_severity(entry.get("severity"), None),
        confidence_modifier=float(entry.get("confidence_modifier", 0.0)),
        stop=bool(entry.get("stop", True)),
    )


def _status(value: Any) -> PluginOutcome | None:
    if value is None:
        return None
    try:
        return PluginOutcome(str(value).upper())
    except ValueError as exc:
        raise ValueError(f"unknown status {value!r}") from exc


def _severity(value: Any, fallback: Severity | None) -> Any:
    if value is None:
        return fallback
    try:
        return Severity(str(value).upper())
    except ValueError as exc:
        raise ValueError(f"unknown severity {value!r}") from exc


__all__ = [
    "Condition",
    "Rule",
    "RuleEngine",
    "RuleOutcome",
    "RuleSet",
    "load_ruleset",
]
