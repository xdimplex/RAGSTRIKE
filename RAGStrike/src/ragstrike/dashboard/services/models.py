"""The UI's own data types.

WHY THE DASHBOARD DEFINES ITS OWN DTOS
    The obvious move is to reuse ``ragstrike.models`` and ``ragstrike.analyzers.base.finding``. The
    dashboard may not import them (ADR-010), and that turns out to be the right constraint rather
    than an annoyance: these types are shaped for *display*, they tolerate fields the backend has
    not started sending yet, and they never fail to construct.

THE PARSING RULE
    Every ``from_payload`` is total. A missing key becomes a documented default; a wrongly typed
    value becomes the default rather than an exception. A dashboard is the tool an operator opens
    *because* something is wrong, so it has to survive a backend that is returning partial data --
    the alternative is a stack trace where the answer should be.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# -------------------------------------------------------------------------------------------------
# Coercion helpers. Small, boring, and used everywhere -- which is exactly why they are one
# implementation rather than an inline `or` at every field.
# -------------------------------------------------------------------------------------------------


def as_str(payload: Mapping[str, Any], key: str, default: str = "") -> str:
    value = payload.get(key, default)
    if value is None or isinstance(value, bool | list | dict):
        return default
    return str(value)


def as_int(payload: Mapping[str, Any], key: str, default: int = 0) -> int:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(payload: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_bool(payload: Mapping[str, Any], key: str, default: bool = False) -> bool:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def as_list(payload: Mapping[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, Sequence):
        return [str(item) for item in value if item is not None]
    return []


def as_mapping(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def parse_timestamp(raw: str) -> datetime | None:
    """Parse an ISO-8601 timestamp, returning ``None`` rather than raising.

    Naive timestamps are read as UTC. The engine emits tz-aware UTC everywhere (a lint rule enforces
    it), so a naive value means an older record or a hand-edited fixture -- assuming UTC is right far
    more often than refusing to display the row.
    """
    text = raw.strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


# -------------------------------------------------------------------------------------------------
# Targets
# -------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Authorization:
    """Who authorized testing this target (ADR-017).

    Displayed on the target card and carried into every report. A target without one is shown with
    a warning rather than hidden -- the operator needs to know it is there and unusable.
    """

    authorized_by: str = ""
    authorization_ref: str = ""
    scope: str = ""

    @property
    def present(self) -> bool:
        return bool(self.authorized_by and self.authorization_ref)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> Authorization:
        return cls(
            authorized_by=as_str(payload, "authorized_by"),
            authorization_ref=as_str(payload, "authorization_ref"),
            scope=as_str(payload, "scope"),
        )


@dataclass(frozen=True, slots=True)
class TargetHealth:
    """The result of a reachability probe."""

    reachable: bool = False
    latency_ms: int = 0
    detail: str = "not probed"
    capabilities: tuple[str, ...] = ()
    checked_at: str = ""

    @property
    def status(self) -> str:
        if not self.checked_at:
            return "unknown"
        return "online" if self.reachable else "offline"

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> TargetHealth:
        return cls(
            reachable=as_bool(payload, "reachable"),
            latency_ms=as_int(payload, "latency_ms"),
            detail=as_str(payload, "detail", "not probed"),
            capabilities=tuple(as_list(payload, "capabilities")),
            checked_at=as_str(payload, "checked_at"),
        )


@dataclass(frozen=True, slots=True)
class TargetView:
    """A configured target, as the Targets page shows it."""

    id: str
    name: str
    url: str
    adapter: str = ""
    kind: str = "rag"
    enabled: bool = True
    timeout_s: float = 120.0
    authorization: Authorization = field(default_factory=Authorization)
    health: TargetHealth = field(default_factory=TargetHealth)
    options: dict[str, Any] = field(default_factory=dict)

    @property
    def is_local(self) -> bool:
        """Whether the URL points at this machine.

        The dashboard *displays* this; it does not enforce it. Scope enforcement lives in
        ``target_adapters.build_adapter`` where it cannot be skipped, and duplicating the rule here
        would create a second implementation that could disagree with the one that matters.
        """
        lowered = self.url.lower()
        return any(
            host in lowered for host in ("//127.0.0.1", "//localhost", "//[::1]", "//0.0.0.0")
        )

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> TargetView:
        name = as_str(payload, "name")
        return cls(
            id=as_str(payload, "id", name),
            name=name,
            url=as_str(payload, "url"),
            adapter=as_str(payload, "adapter"),
            kind=as_str(payload, "kind", "rag"),
            enabled=as_bool(payload, "enabled", True),
            timeout_s=as_float(payload, "timeout", 120.0),
            authorization=Authorization.from_payload(as_mapping(payload, "authorization")),
            health=TargetHealth.from_payload(as_mapping(payload, "health")),
            options=as_mapping(payload, "options"),
        )


# -------------------------------------------------------------------------------------------------
# Plugins
# -------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PluginView:
    """An installed plugin, active or refused."""

    slug: str
    name: str = ""
    version: str = ""
    category: str = ""
    severity: str = "INFO"
    description: str = ""
    author: str = ""
    enabled: bool = True
    status: str = "active"
    requires: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    rejection_reason: str = ""
    attack_count: int = 0
    payload_count: int = 0
    api_version: str = ""

    @property
    def display_name(self) -> str:
        return self.name or self.slug

    @property
    def healthy(self) -> bool:
        return self.status == "active"

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> PluginView:
        slug = as_str(payload, "slug") or as_str(payload, "id")
        return cls(
            slug=slug,
            name=as_str(payload, "name", slug),
            version=as_str(payload, "version"),
            category=as_str(payload, "category"),
            severity=as_str(payload, "severity", "INFO").upper(),
            description=as_str(payload, "description"),
            author=as_str(payload, "author"),
            enabled=as_bool(payload, "enabled", True),
            status=as_str(payload, "status", "active").lower(),
            requires=tuple(as_list(payload, "requires")),
            permissions=tuple(as_list(payload, "permissions")),
            rejection_reason=as_str(payload, "rejection_reason"),
            attack_count=as_int(payload, "attack_count"),
            payload_count=as_int(payload, "payload_count"),
            api_version=as_str(payload, "api_version"),
        )


# -------------------------------------------------------------------------------------------------
# Scans, progress, findings
# -------------------------------------------------------------------------------------------------

#: Scan states that mean "nothing more will happen". Used by the poller to stop polling, which is
#: the difference between a live view and a busy loop against the backend.
TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})

#: Binary units, so a size matches what the operating system reports for the same file.
KIB = 1024
MIB = KIB * KIB


@dataclass(frozen=True, slots=True)
class ScanView:
    """One scan, past or present."""

    id: str
    target: str = ""
    name: str = ""
    profile: str = "standard"
    state: str = "queued"
    started_at: str = ""
    finished_at: str = ""
    duration_s: float = 0.0
    plugins_executed: tuple[str, ...] = ()
    findings_count: int = 0
    severity_counts: dict[str, int] = field(default_factory=dict)
    risk_score: float = 0.0
    grade: str = ""
    coverage: float = 0.0
    outcome: str = ""

    @property
    def finished(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def started(self) -> datetime | None:
        return parse_timestamp(self.started_at)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> ScanView:
        raw_counts = as_mapping(payload, "severity_counts")
        return cls(
            id=as_str(payload, "id") or as_str(payload, "scan_id"),
            target=as_str(payload, "target"),
            name=as_str(payload, "name"),
            profile=as_str(payload, "profile", "standard"),
            state=as_str(payload, "state", "queued").lower(),
            started_at=as_str(payload, "started_at"),
            finished_at=as_str(payload, "finished_at"),
            duration_s=as_float(payload, "duration_s"),
            plugins_executed=tuple(as_list(payload, "plugins_executed")),
            findings_count=as_int(payload, "findings_count"),
            severity_counts={str(k): as_int(raw_counts, str(k)) for k in raw_counts},
            risk_score=as_float(payload, "risk_score"),
            grade=as_str(payload, "grade").upper(),
            coverage=as_float(payload, "coverage"),
            outcome=as_str(payload, "outcome").upper(),
        )


@dataclass(frozen=True, slots=True)
class ScanProgress:
    """A single poll of a running scan.

    ``percent`` is derived from completed/total when the backend does not supply it, so the progress
    bar works against a backend that reports counts but not a percentage.
    """

    scan_id: str
    state: str = "queued"
    completed: int = 0
    total: int = 0
    current_plugin: str = ""
    current_stage: str = ""
    eta_s: float = 0.0
    message: str = ""
    findings_so_far: int = 0
    sequence: int = 0

    @property
    def percent(self) -> float:
        """0.0-1.0. A total of zero reads as 0%, never as a division error or a full bar."""
        if self.state in TERMINAL_STATES:
            return 1.0
        if self.total <= 0:
            return 0.0
        return min(1.0, max(0.0, self.completed / self.total))

    @property
    def finished(self) -> bool:
        return self.state in TERMINAL_STATES

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> ScanProgress:
        return cls(
            scan_id=as_str(payload, "scan_id"),
            state=as_str(payload, "state", "queued").lower(),
            completed=as_int(payload, "completed"),
            total=as_int(payload, "total"),
            current_plugin=as_str(payload, "current_plugin"),
            current_stage=as_str(payload, "current_stage"),
            eta_s=as_float(payload, "eta_s"),
            message=as_str(payload, "message"),
            findings_so_far=as_int(payload, "findings_so_far"),
            sequence=as_int(payload, "sequence"),
        )


@dataclass(frozen=True, slots=True)
class FindingView:
    """One analyzed finding."""

    id: str
    scan_id: str = ""
    plugin: str = ""
    category: str = ""
    title: str = ""
    severity: str = "INFO"
    status: str = "PASS"
    confidence: float = 0.0
    risk_score: float = 0.0
    recommendation: str = ""
    evidence_summary: str = ""
    timestamp: str = ""

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> FindingView:
        evidence = as_mapping(payload, "evidence")
        return cls(
            id=as_str(payload, "id"),
            scan_id=as_str(payload, "scan_id"),
            plugin=as_str(payload, "plugin_id") or as_str(payload, "plugin"),
            category=as_str(payload, "category"),
            title=as_str(payload, "title") or as_str(payload, "category"),
            severity=as_str(payload, "severity", "INFO").upper(),
            status=as_str(payload, "status", "PASS").upper(),
            confidence=as_float(payload, "confidence"),
            risk_score=as_float(payload, "risk_score"),
            recommendation=as_str(payload, "recommendation"),
            evidence_summary=as_str(payload, "evidence_summary") or as_str(evidence, "summary"),
            timestamp=as_str(payload, "timestamp"),
        )


@dataclass(frozen=True, slots=True)
class LogLine:
    """One line in the live log viewer."""

    timestamp: str = ""
    level: str = "INFO"
    message: str = ""
    source: str = ""

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> LogLine:
        return cls(
            timestamp=as_str(payload, "timestamp") or as_str(payload, "ts"),
            level=as_str(payload, "level", "INFO").upper(),
            message=as_str(payload, "message"),
            source=as_str(payload, "source") or as_str(payload, "logger"),
        )


# -------------------------------------------------------------------------------------------------
# Reports
# -------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReportView:
    """A generated report, as the Reports page lists it."""

    id: str
    scan_id: str = ""
    target: str = ""
    fmt: str = "html"
    generated_at: str = ""
    size_bytes: int = 0
    risk_score: float = 0.0
    grade: str = ""
    status: str = ""
    findings_count: int = 0
    report_version: str = ""

    @property
    def size_label(self) -> str:
        if self.size_bytes < KIB:
            return f"{self.size_bytes} B"
        if self.size_bytes < MIB:
            return f"{self.size_bytes / KIB:.1f} KB"
        return f"{self.size_bytes / MIB:.1f} MB"

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> ReportView:
        return cls(
            id=as_str(payload, "id") or as_str(payload, "report_id"),
            scan_id=as_str(payload, "scan_id"),
            target=as_str(payload, "target"),
            fmt=as_str(payload, "format", "html").lower() or as_str(payload, "fmt", "html").lower(),
            generated_at=as_str(payload, "generated_at"),
            size_bytes=as_int(payload, "size_bytes"),
            risk_score=as_float(payload, "risk_score"),
            grade=as_str(payload, "grade").upper(),
            status=as_str(payload, "status").upper(),
            findings_count=as_int(payload, "findings_count"),
            report_version=as_str(payload, "report_version"),
        )


# -------------------------------------------------------------------------------------------------
# System status
# -------------------------------------------------------------------------------------------------

#: The five status values a subsystem can report. ``unknown`` is distinct from ``down`` on purpose:
#: "we could not check" and "we checked and it is broken" call for different operator responses.
COMPONENT_STATES = ("ok", "degraded", "down", "unknown", "disabled")


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    """One subsystem's health."""

    name: str
    status: str = "unknown"
    detail: str = ""
    version: str = ""
    latency_ms: int = 0

    @classmethod
    def from_payload(cls, name: str, payload: Mapping[str, Any]) -> ComponentHealth:
        status = as_str(payload, "status", "unknown").lower()
        return cls(
            name=name,
            status=status if status in COMPONENT_STATES else "unknown",
            detail=as_str(payload, "detail"),
            version=as_str(payload, "version"),
            latency_ms=as_int(payload, "latency_ms"),
        )


@dataclass(frozen=True, slots=True)
class ResourceUsage:
    """Host resources, as reported by the backend.

    Reported by the *backend*, not measured here. The dashboard may run in a different container
    from the engine (the compose file does exactly that), so CPU measured in this process would be
    the CPU of a Streamlit server nobody cares about.
    """

    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    uptime_s: float = 0.0
    available: bool = False

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> ResourceUsage:
        return cls(
            cpu_percent=as_float(payload, "cpu_percent"),
            memory_percent=as_float(payload, "memory_percent"),
            memory_used_mb=as_float(payload, "memory_used_mb"),
            uptime_s=as_float(payload, "uptime_s"),
            available=bool(payload),
        )


@dataclass(frozen=True, slots=True)
class SystemStatus:
    """Everything the System Status page needs, in one object."""

    components: tuple[ComponentHealth, ...] = ()
    resources: ResourceUsage = field(default_factory=ResourceUsage)
    engine_version: str = ""
    plugin_api_version: str = ""
    scoring_model_version: str = ""
    checked_at: str = ""

    @property
    def overall(self) -> str:
        """Worst-wins, with ``disabled`` excluded -- a subsystem that is off on purpose is not a
        degradation."""
        live = [c.status for c in self.components if c.status != "disabled"]
        for state in ("down", "degraded", "unknown"):
            if state in live:
                return state
        return "ok" if live else "unknown"


# -------------------------------------------------------------------------------------------------
# Search
# -------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One global-search result, with enough context to navigate to it."""

    kind: str
    id: str
    title: str
    subtitle: str = ""
    page_id: str = ""
    score: float = 0.0
