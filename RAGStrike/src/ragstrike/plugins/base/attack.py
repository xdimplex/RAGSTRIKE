"""``BaseAttack`` -- the contract every attack plugin implements.

**The load-bearing abstraction of the framework.** Adding a new attack technique requires zero
edits under ``core/``. If you ever change the engine to add an attack, that is a gap in this
contract and it should be reported as one -- there is a test (``test_no_plugin_name_appears...``)
that walks the engine's AST to enforce it.

Two styles are supported, and both produce identical behaviour:

**Declarative** -- set class attributes and implement only the methods your attack actually needs::

    class MyAttack(BaseAttack):
        plugin_id = "my-attack"
        plugin_name = "My Attack"
        plugin_version = "1.0.0"
        author = "Me"
        description = "..."
        category = "diagnostic"
        severity = Severity.LOW

        def payloads(self):
            return [Payload(id="p1", content="ping")]
        async def execute(self, target, payloads):
            ...
        def analyze(self, records):
            return Analysis(outcome=PluginOutcome.PASS, summary="ok")
        def recommendation(self, analysis):
            return Recommendation(title="none", remediation="none")

**Imperative** -- override :meth:`metadata` when identity is computed at runtime.

Both styles produce the same :class:`AttackMetadata`. The default implementation of ``metadata()``
reads the class attributes; overriding it replaces that behaviour.

The nine methods below are called in a fixed order (lifecycle diagram in
``docs/plugin-lifecycle.md``)::

    validate()      -> once, at load time. Refuses malformed plugins.
    healthcheck()   -> once, before setup. Refuses plugins that cannot run today.
    setup()         -> once per scan, before any payloads.
    payloads()      -> once per scan, must be deterministic.
    execute()       -> once per scan. THE ONLY METHOD THAT DOES I/O.
    analyze()       -> once per scan. PURE. Replay depends on it.
    recommendation()-> once per scan.
    cleanup()       -> once per scan, always. Even on error.
    metadata()      -> may be called at any time. Also pure.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from ragstrike.core.contracts.target_adapter import TargetAdapter
from ragstrike.models.values.enums import Capability, PluginOutcome, Severity
from ragstrike.plugins.base.context import PluginContext
from ragstrike.plugins.base.reports import Check, HealthReport, ValidationReport

if TYPE_CHECKING:  # pragma: no cover
    from ragstrike.plugins.base.payloads import PayloadLoader


@dataclass(frozen=True, slots=True)
class AttackMetadata:
    """Everything the engine needs to know before running a plugin.

    Assembled by :meth:`BaseAttack.metadata`. Read from the plugin's ``metadata.yaml`` where
    possible, so the registry can decide compatibility and capability fit **before importing any
    plugin code** (ADR-003).
    """

    slug: str
    name: str
    version: str
    category: str
    description: str = ""
    severity: Severity = Severity.INFO
    author: str = ""
    #: Attacks declaring capabilities the target lacks are SKIPPED and recorded as a coverage gap,
    #: never silently dropped.
    requires_capabilities: tuple[Capability, ...] = (Capability.CHAT,)
    owasp_llm: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    #: e.g. ``"rag"``, ``"chat-only"``. Advisory: the scheduler uses capabilities as the machine
    #: check; this is documentation for humans and future filtering.
    required_target_type: str = "any"
    #: Minimum RAGStrike engine version. Rejected if the running engine is older.
    min_framework_version: str = "0.3.0"
    #: SemVer range against ``PLUGIN_API_VERSION``, not against the application version (ADR-015).
    requires_api: str = ">=1.0,<2.0"
    license: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "version": self.version,
            "category": self.category,
            "description": self.description,
            "severity": self.severity.value,
            "author": self.author,
            "requires_capabilities": [c.value for c in self.requires_capabilities],
            "owasp_llm": list(self.owasp_llm),
            "references": list(self.references),
            "tags": list(self.tags),
            "required_target_type": self.required_target_type,
            "min_framework_version": self.min_framework_version,
            "requires_api": self.requires_api,
            "license": self.license,
        }


@dataclass(frozen=True, slots=True)
class Payload:
    """One concrete test input.

    Payloads are **data, never code** (ADR-016). They are rendered by a non-evaluating template
    engine, which is what lets security researchers who are not Python developers contribute, and
    what keeps the scanner's own attack surface small.
    """

    id: str
    content: str
    tier: str = "standard"
    #: What success would look like. Phase 6's analyzer consumes this; earlier phases only carry it.
    expects: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    """One payload sent, one response received. Immutable evidence."""

    payload_id: str
    prompt: str
    response: Any  # TargetResponse, kept as Any to avoid a redundant import here
    elapsed_ms: int = 0
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and getattr(self.response, "ok", True)


@dataclass(frozen=True, slots=True)
class Analysis:
    """The verdict, from the defender's point of view.

    ``PASS`` means the target resisted. ``FAIL`` means it is vulnerable. The convention is fixed
    here and translated nowhere else.
    """

    outcome: PluginOutcome
    summary: str
    detail: str = ""
    confidence: float = 1.0
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Recommendation:
    """What to do about a failure.

    Retrieved from the plugin, not generated at runtime (ADR-019). A security report is a
    compliance artifact, and advice that differs for every reader of the same finding is not one.
    """

    title: str
    remediation: str
    references: tuple[str, ...] = ()
    effort: str = "MEDIUM"


class BaseAttack(abc.ABC):
    """Base class for every attack plugin.

    Subclass it, set the class attributes, implement ``execute``/``analyze``/``recommendation``/
    ``payloads``, drop the folder into ``plugins/``. There is no registration step: discovery is
    automatic and no plugin name appears anywhere in the engine.

    See the module docstring for the lifecycle.
    """

    # -- declarative identity -----------------------------------------------------------------
    #
    # Class attributes read by the default :meth:`metadata`. Plugins may set any or all of them;
    # any that a plugin does not set fall back to the class default here. Overriding metadata()
    # replaces this behaviour entirely.

    plugin_id: ClassVar[str] = ""
    plugin_name: ClassVar[str] = ""
    plugin_version: ClassVar[str] = "0.0.0"
    author: ClassVar[str] = ""
    description: ClassVar[str] = ""
    category: ClassVar[str] = "uncategorized"
    severity: ClassVar[Severity] = Severity.INFO
    owasp_mapping: ClassVar[tuple[str, ...]] = ()
    references: ClassVar[tuple[str, ...]] = ()
    tags: ClassVar[tuple[str, ...]] = ()
    requires_capabilities: ClassVar[tuple[Capability, ...]] = (Capability.CHAT,)
    required_target_type: ClassVar[str] = "any"
    min_framework_version: ClassVar[str] = "0.3.0"
    requires_api: ClassVar[str] = ">=1.0,<2.0"
    license: ClassVar[str] = ""
    #: Default enablement, overridden by ``plugins.yaml``. The engine's PluginManager writes here
    #: at runtime after reading configuration.
    enabled: ClassVar[bool] = True

    # -- construction -------------------------------------------------------------------------

    def __init__(
        self,
        *,
        context: PluginContext | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        """DI happens here.

        Args:
            context: The :class:`PluginContext` the framework built. When absent (tests, ad-hoc
                usage), a minimal placeholder is synthesised so ``self.context`` is always valid.
            options: Legacy parameter kept for tests that predate the context. Merged into the
                context's config with lower precedence.
        """
        if context is None:
            context = PluginContext.for_plugin(
                plugin_id=self.plugin_id or type(self).__name__.lower(),
                source=Path(),
                config=dict(options or {}),
            )
        elif options:
            merged = {**options, **context.config}
            context = PluginContext(
                plugin_id=context.plugin_id,
                source=context.source,
                payload_dir=context.payload_dir,
                config=merged,
                timeout_s=context.timeout_s,
                severity_override=context.severity_override,
                logger=context.logger,
            )
        self.context = context

    @property
    def options(self) -> dict[str, Any]:
        """Backwards-compatible shorthand for ``self.context.config``.

        Phase 3 plugins used ``self.options`` directly. Kept so existing plugins keep working.
        """
        return self.context.config

    # -- metadata (default reads the class attributes) ---------------------------------------

    def metadata(self) -> AttackMetadata:
        """Assemble identity from the class attributes.

        Override this method when identity is computed at runtime (rare). When overridden, the
        class attributes above are ignored -- the returned object wins.
        """
        return AttackMetadata(
            slug=self.plugin_id or type(self).__name__.lower(),
            name=self.plugin_name or self.plugin_id or type(self).__name__,
            version=self.plugin_version,
            category=self.category,
            description=self.description,
            severity=_resolve_severity(self.severity, self.context.severity_override),
            author=self.author,
            requires_capabilities=self.requires_capabilities,
            owasp_llm=self.owasp_mapping,
            references=self.references,
            tags=self.tags,
            required_target_type=self.required_target_type,
            min_framework_version=self.min_framework_version,
            requires_api=self.requires_api,
            license=self.license,
        )

    # -- required behavioural methods --------------------------------------------------------

    @abc.abstractmethod
    def payloads(self) -> list[Payload]:
        """The inputs this attack will send.

        Called once per scan, before execution. **Must be deterministic**: the same plugin with
        the same options must produce the same payloads in the same order, or scan results stop
        being comparable across runs.

        A plugin that stores payloads on disk can call :meth:`load_payloads` for the common case.
        """

    @abc.abstractmethod
    async def execute(
        self, target: TargetAdapter, payloads: list[Payload]
    ) -> list[ExecutionRecord]:
        """Send *payloads* to *target* and record what came back.

        **The only method that performs I/O.** It must not decide whether the attack succeeded --
        that is :meth:`analyze`, and keeping them separate is what makes offline replay possible
        (ADR-004, ADR-012).

        A failing payload should be captured as an :class:`ExecutionRecord` carrying ``error``,
        not raised: one bad payload must not lose the other nineteen.
        """

    @abc.abstractmethod
    def analyze(self, records: list[ExecutionRecord]) -> Analysis:
        """Decide whether the target is vulnerable.

        **Pure.** No network, no filesystem, no clock, no randomness. Given the same records it
        must return the same analysis, on any machine, every time. Without that property, Phase 5's
        replay harness cannot re-run analysis over stored evidence -- and detector development
        becomes a slow, nondeterministic loop instead of a fast offline one.
        """

    @abc.abstractmethod
    def recommendation(self, analysis: Analysis) -> Recommendation:
        """What the operator should do about *analysis*.

        Retrieved from the plugin's catalog (ADR-019). Never generated at runtime -- a security
        report is a compliance artifact and advice that differs for every reader of the same
        finding is not one.
        """

    # -- optional lifecycle hooks (defaults are no-ops) --------------------------------------

    def setup(self) -> None:  # noqa: B027 - intentional no-op default; override to allocate
        """Prepare state before ``execute()``.

        The default is a no-op. Override to allocate resources, warm caches, or plant canaries.
        Anything created here should be released in :meth:`cleanup`, which the scheduler
        guarantees to call even on error.
        """

    def cleanup(self) -> None:  # noqa: B027 - intentional no-op default; override to release
        """Release resources allocated by ``setup()``.

        The default is a no-op. **Always called**, even when ``execute()`` raised or the scan was
        cancelled -- the scheduler wraps the whole per-plugin call in ``try/finally`` around this
        method.
        """

    def healthcheck(self) -> HealthReport:
        """Is this plugin able to run right now?

        The default reports healthy. Override when a plugin needs to confirm it can operate
        against the current target (e.g. its detectors need a canary and the adapter has to
        support ingest). A plugin whose healthcheck fails is recorded SKIPPED with the failing
        rule's detail -- distinguished from skipped-for-capability so operators can tell "cannot
        help against this target" from "broken today".
        """
        return HealthReport.ok()

    def validate(self) -> ValidationReport:
        """Is this plugin correctly configured?

        Called by the registry at **load time**, not per scan. The default checks a small handful
        of always-required invariants (a slug, a non-``0.0.0`` version, at least one capability).
        Override for plugin-specific rules (e.g. "my payload set is present and non-empty").

        A plugin whose validation fails is rejected at load time, appears in the health report,
        and never runs. Rejection is never silent -- ``ragstrike plugins`` shows both the active
        and refused lists.
        """
        meta = self.metadata()
        return ValidationReport(
            checks=[
                Check(rule="has-slug", passed=bool(meta.slug), detail=""),
                Check(
                    rule="non-zero-version",
                    passed=meta.version != "0.0.0",
                    detail="plugin_version is the default 0.0.0" if meta.version == "0.0.0" else "",
                ),
                Check(
                    rule="declares-capability",
                    passed=bool(meta.requires_capabilities),
                    detail=(
                        "requires_capabilities is empty" if not meta.requires_capabilities else ""
                    ),
                ),
            ]
        )

    # -- helpers ------------------------------------------------------------------------------

    def load_payloads(self) -> list[Payload]:
        """Read every payload from ``self.context.payload_dir``.

        The convenience path for plugins whose payloads are on disk. Handles JSON, YAML, and TXT
        transparently. Plugins that generate payloads programmatically simply override
        :meth:`payloads` and ignore this.
        """
        # Local import: payloads imports from this module (for Payload), so a top-level import
        # here would be a cycle.
        from ragstrike.plugins.base.payloads import PayloadLoader  # noqa: PLC0415

        loader: PayloadLoader = PayloadLoader(self.context.payload_dir)
        return loader.all()

    def applies_to(self, capabilities: tuple[Capability, ...]) -> bool:
        """Whether this attack can run against a target with *capabilities*.

        The default checks ``requires_capabilities``. Override only for genuinely conditional
        logic; overstating applicability wastes a case, understating it hides a coverage gap.
        """
        required = self.metadata().requires_capabilities
        if not capabilities:
            return True  # unverified target -- attempt, rather than skip everything
        return all(capability in capabilities for capability in required)

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        meta = self.metadata()
        return f"<{type(self).__name__} {meta.slug}@{meta.version}>"


def _resolve_severity(default: Severity, override: str | None) -> Severity:
    """Apply an operator's ``severity_override`` from ``plugins.yaml``, if any."""
    if not override:
        return default
    try:
        return Severity(override.upper())
    except ValueError:
        # Bad overrides are ignored rather than fatal -- a typo in plugins.yaml should not stop a
        # scan. The registry logs it during config load.
        return default
