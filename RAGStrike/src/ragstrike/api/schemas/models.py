"""Request and response models.

Pydantic belongs at a boundary and nowhere else. Domain entities stay frozen dataclasses; these are
their wire representations, and the mapping between the two is explicit rather than automatic.

WHY THE RESPONSE MODELS ARE EXPLICIT RATHER THAN GENERATED FROM THE ENTITIES
    A generated schema leaks whatever the entity happens to hold. That is how an ``options`` dict
    containing a target's credential, or a raw evidence blob containing document text, ends up in an
    HTTP response nobody meant to expose. Listing the fields means adding one is a decision.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ComponentHealth(BaseModel):
    status: str = Field(description="ok | degraded | down")
    detail: str = ""
    version: str = ""
    latency_ms: int | None = None


class HealthResponse(BaseModel):
    status: str = Field(description="ok when every component is ok, otherwise degraded")
    components: dict[str, ComponentHealth]
    checked_at: datetime


class VersionResponse(BaseModel):
    engine: str
    plugin_api: str
    scoring_model: str
    report_formats: dict[str, bool]


class ProfileOut(BaseModel):
    id: str
    name: str
    description: str
    packs: list[str]
    payload_tiers: list[str]
    attempts: int


class ProfileList(BaseModel):
    profiles: list[ProfileOut]


class AuthorizationOut(BaseModel):
    authorized_by: str
    authorization_ref: str
    scope: str


class TargetOut(BaseModel):
    """A configured target.

    ``options`` is **not** exposed. It carries adapter configuration including the ``auth`` block,
    and while that block holds an environment variable *name* rather than a secret, publishing an
    inventory of which variables hold which credentials is free reconnaissance.
    """

    name: str
    adapter: str
    url: str
    timeout_s: int
    enabled: bool
    authorized: bool
    authorization: AuthorizationOut | None = None
    capabilities: list[str] = Field(default_factory=list)


class TargetList(BaseModel):
    targets: list[TargetOut]


class VerifyResponse(BaseModel):
    name: str
    reachable: bool
    latency_ms: int
    detail: str


class PackOut(BaseModel):
    slug: str
    name: str
    version: str
    category: str
    severity: str
    enabled: bool
    requires: list[str] = Field(default_factory=list)
    #: How many test inputs this pack will actually send -- ``len(attack.payloads())``, the same
    #: call the scheduler makes. Zero means the pack declined to enumerate them (see ``_payloads``).
    payloads: int = 0
    #: The rest of what ``ragstrike plugins info`` shows. The manager has had all of it since
    #: Phase 4; none of it was ever put on the wire, so the dashboard's Metadata popover rendered a
    #: blank author, a blank description, and "Permissions: none" for every pack -- including the
    #: packs whose permissions are the reason another one was refused.
    description: str = ""
    author: str = ""
    permissions: list[str] = Field(default_factory=list)
    api_version: str = ""


class PackCheckOut(BaseModel):
    """One validation rule and its outcome."""

    name: str
    passed: bool
    detail: str = ""


class PackValidationOut(BaseModel):
    """The result of re-validating an installed pack.

    Field names match what the dashboard already reads (`valid`, `checks[].name/passed/detail`) --
    it has rendered this shape since Phase 12 against an endpoint that did not exist.
    """

    slug: str
    valid: bool
    checks: list[PackCheckOut] = Field(default_factory=list)


class PackList(BaseModel):
    packs: list[PackOut]
    refused: list[dict[str, str]] = Field(default_factory=list)


class ScanRequest(BaseModel):
    """Start a scan.

    THE FIELD NAMES COME FROM THE DASHBOARD, NOT FROM THIS FILE
        The dashboard has posted ``{target, profile, name, plugins, categories}`` since Phase 12.
        The first version of this schema accepted only ``{target, profile, acknowledge}`` with
        ``extra="forbid"``, so every Start Scan click was rejected with a 422 -- and the Phase 16
        report claimed no dashboard change was needed because the routes matched. The routes did
        match. Nobody checked the bodies.

        When a client and a server disagree about a contract that predates the server, the server is
        the one that is wrong.

    ``acknowledge`` is required and must be true. The API is a second front door to a tool that
    sends attack payloads at a live system; a POST that starts one on default arguments alone is a
    footgun, and ADR-017 already establishes that authorization is an explicit act rather than an
    assumed one. The dashboard calls the same idea ``authorized``, so both spellings are accepted --
    a client should not have to guess which synonym the server picked.
    """

    model_config = ConfigDict(extra="forbid")

    target: str
    profile: str | None = None
    #: Human label for this run. Recorded, never used to make a decision.
    name: str = ""
    #: Ad-hoc pack selection. Empty means "whatever the profile says".
    plugins: list[str] = Field(default_factory=list)
    #: Ad-hoc category selection, resolved to pack slugs against the registry.
    categories: list[str] = Field(default_factory=list)
    acknowledge: bool = Field(
        default=False,
        description="Must be true. Confirms the caller intends to attack the named target.",
    )
    authorized: bool = Field(
        default=False,
        description="Alias for `acknowledge`; the name the dashboard has always used.",
    )

    @property
    def confirmed(self) -> bool:
        """Either spelling counts. Both mean the caller said yes on purpose."""
        return self.acknowledge or self.authorized


class ScanAccepted(BaseModel):
    """The 202 body.

    Carries the identifier under **both** names. The dashboard has read ``id`` since Phase 12; the
    rest of this API says ``scan_id``. Emitting one and not the other means whichever client was not
    consulted breaks -- and the dashboard was the one not consulted.
    """

    scan_id: str
    #: The same value. Kept for the dashboard, which reads this key.
    id: str = ""
    state: str
    target: str


class ScanOut(BaseModel):
    """One scan, shaped for the client that reads it.

    THE FIELD LIST IS THE DASHBOARD'S, NOT THIS FILE'S
        The first version emitted only counts. The dashboard reads ``name``, ``profile``,
        ``duration_s``, ``findings_count``, ``severity_counts``, ``risk_score``, ``grade`` and
        ``outcome`` -- none of which were sent -- and reads ``plugins_executed`` as a **list of
        slugs**, where an integer was sent instead.

        Every one of those fell back to its default, so a scan that ran correctly rendered as
        ``RISK 0.0/100``, ``DURATION 0s``, ``PLUGINS EXECUTED 0``, grade ``?``, and profile
        ``standard`` regardless of the profile actually used. Only ``coverage`` happened to line up.
    """

    scan_id: str
    #: Duplicated as ``id`` for the dashboard, which keys on that. See :class:`ScanAccepted`.
    id: str = ""
    target: str
    name: str = ""
    profile: str = ""
    state: str
    outcome: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_s: float = 0.0
    #: The slugs that actually ran. A list, because the client renders its length *and* its
    #: contents; an integer gives it neither.
    plugins_executed: list[str] = Field(default_factory=list)
    #: How many packs ran, as a number rather than a list length.
    #:
    #: The listing cannot fill ``plugins_executed`` without a query per row, so it used to send an
    #: empty list -- and the dashboard, which renders ``len(plugins_executed)``, showed **PLUGINS 0**
    #: for every scan, including a 23-minute full-coverage run. The count is on the session already;
    #: only the wire format had no place to put it.
    plugins_executed_count: int = 0
    plugins_total: int = 0
    plugins_passed: int = 0
    plugins_failed: int = 0
    plugins_errored: int = 0
    plugins_skipped: int = 0
    findings_count: int = 0
    severity_counts: dict[str, int] = Field(default_factory=dict)
    risk_score: float = 0.0
    grade: str = ""
    coverage: float = 0.0
    error: str = ""


class ScanList(BaseModel):
    scans: list[ScanOut]


class LogLineOut(BaseModel):
    """One line of a scan's log, as the dashboard's log pane consumes it."""

    timestamp: str = ""
    level: str = "INFO"
    source: str = ""
    message: str = ""


class LogList(BaseModel):
    """Response for ``GET /scans/{id}/logs``."""

    lines: list[LogLineOut] = Field(default_factory=list)


class ScanComparisonOut(BaseModel):
    """Posture delta between two scans, for the Scan History page's Compare panel.

    The three lists hold **plugin slugs**, not finding ids. Finding ids are minted per scan and
    never recur, so a slug is the only thing that can answer "is that problem still there".
    """

    base: ScanOut
    head: ScanOut
    #: Failing in head, not in base -- a regression.
    new: list[str] = Field(default_factory=list)
    #: Failing in base, not in head -- remediated, or no longer exercised.
    fixed: list[str] = Field(default_factory=list)
    #: Failing in both.
    persisting: list[str] = Field(default_factory=list)


class ProgressOut(BaseModel):
    scan_id: str
    state: str
    completed: int
    total: int
    percent: float
    current: str = ""


class FindingOut(BaseModel):
    finding_id: str
    plugin: str
    category: str
    status: str
    severity: str
    confidence: float
    risk_score: float
    description: str = ""
    recommendation: str = ""
    #: When the analyzer produced this finding. The entity has carried it all along; leaving it out
    #: of the response left the findings table's "When" column blank on every row.
    timestamp: datetime | None = None
    #: A one-line summary of the normalized evidence, so the table can say what was observed without
    #: shipping the whole evidence blob to draw a row.
    evidence_summary: str = ""


class FindingList(BaseModel):
    findings: list[FindingOut]
    coverage: float = 0.0


class ReportRequest(BaseModel):
    """Generate a report.

    Accepts ``format`` (singular string) as well as ``formats`` (list). The dashboard has posted
    ``{"format": "pdf"}`` since Phase 12; this schema originally accepted only the plural list and
    rejected every Generate Report click with a 422.
    """

    model_config = ConfigDict(extra="forbid")

    formats: list[str] = Field(default_factory=list)
    #: The dashboard's spelling. Folded into :meth:`chosen`.
    format: str = ""

    def chosen(self) -> list[str]:
        """The formats to render, from either spelling. Defaults to HTML."""
        if self.formats:
            return self.formats
        return [self.format] if self.format else ["html"]


class ReportOut(BaseModel):
    report_id: str
    scan_id: str
    generated_at: datetime
    formats: dict[str, str] = Field(default_factory=dict)


class ReportSummaryOut(BaseModel):
    """One row of the report history.

    Metadata only. ``content`` is excluded on purpose -- a listing that carried every rendered
    document would ship megabytes to draw a table. The body comes from the open-report route.
    """

    report_id: str
    scan_id: str
    #: The NAME the operator gave the scan this report covers -- "vulnerable-rag standard sweep",
    #: not "94b091f7d42b4953b80337e6d74155d3". Resolved from the scan record at listing time rather
    #: than stored on the report, so reports generated before this field existed carry it too.
    scan_name: str = ""
    title: str = ""
    target: str = ""
    format: str = ""
    finding_count: int = 0
    risk_score: float = 0.0
    #: The scan's letter grade, by the same rule the scan listing uses -- including ``?`` for a scan
    #: nobody can grade honestly. Without it the Reports page had a Grade column that read ``--`` on
    #: every row and a badge that always said UNGRADED.
    grade: str = ""
    status: str = ""
    size_bytes: int = 0
    generated_at: datetime


class ReportList(BaseModel):
    """Response for ``GET /reports``.

    Holds summaries rather than :class:`ReportOut`: that model describes the *result of generating*
    a report (which formats were written where), not a stored one. This schema existed unused until
    the listing route was added, so nothing had to migrate.
    """

    reports: list[ReportSummaryOut]


class ErrorBody(BaseModel):
    """Documented so the envelope appears in the OpenAPI schema rather than only in prose."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = ""


class ErrorResponse(BaseModel):
    error: ErrorBody


__all__ = [
    "AuthorizationOut",
    "ComponentHealth",
    "ErrorResponse",
    "FindingList",
    "FindingOut",
    "HealthResponse",
    "PackList",
    "PackOut",
    "ProfileList",
    "ProfileOut",
    "ProgressOut",
    "ReportList",
    "ReportOut",
    "ReportRequest",
    "ScanAccepted",
    "ScanList",
    "ScanOut",
    "ScanRequest",
    "TargetList",
    "TargetOut",
    "VerifyResponse",
    "VersionResponse",
]
