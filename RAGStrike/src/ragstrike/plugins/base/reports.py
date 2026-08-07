"""Health and validation reports returned by a plugin.

Two shapes; both are lists of checks, each of which carries whether it passed and a short human
message. That symmetry is deliberate: the CLI renders both with the same table code, and any
future dashboard can too.

The distinction between them is *when they run*:

* ``validate()`` is called at load time by the registry. It answers "should this plugin exist as
  a runnable thing?" and returns a :class:`ValidationReport`.
* ``healthcheck()`` is called before execution. It answers "can this plugin run right now?" -- a
  plugin that needs a corpus canary might report healthy only after a target confirms the
  ingestion capability. Returns a :class:`HealthReport`.

Both default to a no-op ``OK`` result, so plugins that need neither can ignore both methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Check:
    """One rule the plugin ran, with its outcome.

    The ``rule`` slug is machine-readable so a CI job can key off it (e.g. "missing-payloads"
    always maps to a fixable configuration error), and the ``detail`` field explains it to a
    human.
    """

    rule: str
    passed: bool
    detail: str = ""

    @property
    def failed(self) -> bool:
        return not self.passed


@dataclass(frozen=True, slots=True)
class HealthReport:
    """The result of ``healthcheck()``.

    A plugin whose report has any failing check will be recorded as SKIPPED with the failure
    detail; it never runs. Skipped-for-health is distinguished from skipped-for-capability in the
    result summary so an operator can tell "this plugin cannot help against this target" from
    "this plugin is broken today".
    """

    checks: list[Check] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def healthy(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_checks(self) -> list[Check]:
        return [check for check in self.checks if check.failed]

    @classmethod
    def ok(cls) -> HealthReport:
        return cls(checks=[Check(rule="healthy", passed=True)])


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """The result of ``validate()``, called at load time by the registry.

    A plugin whose validation report has any failing check is rejected -- it does not become a
    scannable plugin, and the reason is recorded in :class:`~ragstrike.plugins.registry.plugin_registry.PluginHealth.rejected`
    with the same "never silent" rule that governs every other refusal.
    """

    checks: list[Check] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [check for check in self.checks if check.failed]

    def merge(self, other: ValidationReport) -> ValidationReport:
        """Combine two reports. Used when framework-level and plugin-level validation both run."""
        return ValidationReport(checks=[*self.checks, *other.checks])

    @classmethod
    def ok(cls) -> ValidationReport:
        return cls(checks=[Check(rule="valid", passed=True)])
