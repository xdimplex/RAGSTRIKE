"""Service tests.

THE CLAIMS UNDER TEST

1. **Services contain no UI.** Enforced structurally by a test that reads the source: no service
   imports Streamlit, directly or by name.
2. **Every service is total.** A backend returning partial, wrongly typed, or absent data produces a
   usable object rather than an exception. A dashboard is what you open *because* something is
   wrong; it cannot be the second thing that breaks.
3. **The error taxonomy is honest.** Each failure the brief names maps onto a class that phrases it
   for an operator and says what to do next.
4. **The safety rules stay where they are enforced.** The dashboard shows the local-only policy; it
   does not re-implement it. Two implementations of "is this host allowed" fail by the permissive
   one winning.

Everything runs against a fake transport -- no network, no server, no monkeypatching.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from ragstrike.dashboard.config import DashboardConfig
from ragstrike.dashboard.services import build_services_with
from ragstrike.dashboard.services.demo import DemoTransport
from ragstrike.dashboard.services.errors import (
    BackendRequestError,
    BackendUnavailableError,
    ConfigurationProblemError,
    DashboardError,
    DatabaseFailureError,
    NotImplementedByBackendError,
    PluginFailureError,
    ReportFailureError,
    ScanRejectedError,
    TargetMissingError,
    from_envelope,
)
from ragstrike.dashboard.services.models import (
    FindingView,
    PluginView,
    ReportView,
    ScanProgress,
    ScanView,
    SystemStatus,
    TargetView,
    parse_timestamp,
)
from ragstrike.dashboard.services.report_service import ReportService
from ragstrike.dashboard.services.scan_service import ScanProfile, ScanRequest, should_poll
from ragstrike.dashboard.services.settings_service import SettingsService, is_sensitive, redact
from ragstrike.dashboard.services.status_service import SUBSYSTEMS, StatusService
from ragstrike.dashboard.services.target_service import looks_local
from ragstrike.dashboard.services.transport import HttpTransport, build_transport

SERVICES_DIR = Path("src/ragstrike/dashboard/services")


class FakeTransport:
    """Answers from a fixed routing table, and records what it was asked."""

    name = "fake"

    def __init__(self, responses: Mapping[str, Any] | None = None) -> None:
        self.responses = dict(responses or {})
        self.calls: list[tuple[str, str]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> Any:
        self.calls.append((method.upper(), path))
        key = f"{method.upper()} {path}"
        if key in self.responses:
            value = self.responses[key]
            if isinstance(value, Exception):
                raise value
            return value
        if path in self.responses:
            return self.responses[path]
        raise NotImplementedByBackendError(key)


def services(responses: Mapping[str, Any] | None = None) -> Any:
    return build_services_with(FakeTransport(responses))


def demo() -> Any:
    return build_services_with(DemoTransport())


# -- the structural claim --------------------------------------------------------------------------


def test_no_service_imports_streamlit() -> None:
    """ "Services must never contain UI", made checkable.

    Reads the source rather than trusting review: a deferred ``import streamlit`` inside a function
    would still be a service that knows about the UI.
    """
    offenders = [
        path.name
        for path in SERVICES_DIR.glob("*.py")
        if "streamlit" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_no_service_imports_an_engine_package() -> None:
    """ADR-010, spot-checked at the source level. ``lint-imports`` is the real gate; this one fails
    faster and says which file.

    Parses the AST rather than grepping the text: several of these modules *discuss* the engine
    packages in their docstrings, explaining why they may not import them, and a substring match
    flags the explanation as the violation.
    """
    import ast

    forbidden = ("ragstrike.core", "ragstrike.models", "ragstrike.database", "ragstrike.analyzers")
    offenders: list[str] = []

    for path in SERVICES_DIR.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if any(name.startswith(marker) for name in names for marker in forbidden):
                offenders.append(f"{path.name}:{node.lineno}")

    assert offenders == []


# -- parsing is total ------------------------------------------------------------------------------


def test_every_dto_constructs_from_an_empty_payload() -> None:
    """The backend does not exist yet and will grow fields over time. Nothing here may raise on a
    key that has not been invented."""
    for cls in (TargetView, PluginView, ScanView, ScanProgress, FindingView, ReportView):
        assert cls.from_payload({}) is not None


def test_a_wrongly_typed_field_falls_back_instead_of_raising() -> None:
    view = ScanView.from_payload({"risk_score": "not a number", "findings_count": None})

    assert view.risk_score == 0.0
    assert view.findings_count == 0


def test_booleans_are_not_silently_read_as_numbers() -> None:
    """``True`` is an ``int`` in Python. A backend sending ``findings_count: true`` should not
    produce a scan with one finding."""
    assert ScanView.from_payload({"findings_count": True}).findings_count == 0


def test_a_target_id_defaults_to_its_name() -> None:
    """Targets are named in ``targets.yaml`` and may have no separate id."""
    assert TargetView.from_payload({"name": "vulnerable-rag"}).id == "vulnerable-rag"


def test_a_finding_reads_its_plugin_from_either_field_name() -> None:
    assert FindingView.from_payload({"plugin_id": "p"}).plugin == "p"
    assert FindingView.from_payload({"plugin": "p"}).plugin == "p"


def test_an_evidence_summary_is_found_inside_the_evidence_object() -> None:
    view = FindingView.from_payload({"evidence": {"summary": "canary observed"}})

    assert view.evidence_summary == "canary observed"


def test_a_naive_timestamp_is_read_as_utc() -> None:
    """The engine emits tz-aware UTC everywhere (a lint rule enforces it), so a naive value means an
    old record. Assuming UTC beats refusing to display the row."""
    parsed = parse_timestamp("2026-07-30T12:00:00")

    assert parsed is not None
    assert parsed.tzinfo is not None


def test_an_unparseable_timestamp_returns_none_rather_than_raising() -> None:
    assert parse_timestamp("last tuesday") is None


def test_a_comma_separated_list_is_accepted_where_a_list_is_expected() -> None:
    assert PluginView.from_payload({"requires": "CHAT, RETURN_CHUNKS"}).requires == (
        "CHAT",
        "RETURN_CHUNKS",
    )


# -- targets ---------------------------------------------------------------------------------------


def test_listing_targets_parses_the_collection() -> None:
    service = services({"/targets": {"targets": [{"name": "a"}, {"name": "b"}]}}).targets

    assert [t.name for t in service.list_targets()] == ["a", "b"]


def test_a_malformed_target_collection_yields_no_targets_rather_than_an_error() -> None:
    assert services({"/targets": {"targets": "nope"}}).targets.list_targets() == []


def test_enabled_targets_are_offered_first() -> None:
    service = services(
        {"/targets": {"targets": [{"name": "off", "enabled": False}, {"name": "on"}]}}
    ).targets

    assert service.names() == ["on", "off"]


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:9000", "http://localhost:8000", "http://[::1]:9000"],
)
def test_loopback_urls_are_recognised_as_local(url: str) -> None:
    assert looks_local(url)


@pytest.mark.parametrize("url", ["https://example.com", "http://10.0.0.5:9000"])
def test_non_loopback_urls_are_not(url: str) -> None:
    assert not looks_local(url)


def test_the_dashboard_does_not_enforce_scope_itself() -> None:
    """It *shows* the policy; ``target_adapters.build_adapter`` enforces it on every path. A second
    implementation here would be a second opinion, and the permissive one would win by accident.

    So: creating a non-local target is passed to the backend, which refuses it.
    """
    transport = FakeTransport({"POST /targets": {"name": "remote", "url": "https://example.com"}})

    created = build_services_with(transport).targets.create_target(
        {"name": "remote", "url": "https://example.com"}
    )

    assert created.name == "remote"
    assert ("POST", "/targets") in transport.calls


def test_a_missing_target_gets_its_own_error() -> None:
    with pytest.raises(TargetMissingError):
        demo().targets.get_target("no-such-target")


def test_verifying_a_target_goes_through_the_backend() -> None:
    """The dashboard never opens a socket to a scan target itself -- that would be network egress
    from the UI process, which the ADR-010 separation exists to prevent."""
    transport = FakeTransport({"POST /targets/t/verify": {"reachable": True, "latency_ms": 9}})

    health = build_services_with(transport).targets.test_connection("t")

    assert health.reachable
    assert transport.calls == [("POST", "/targets/t/verify")]


# -- plugins ---------------------------------------------------------------------------------------


def test_the_inventory_separates_active_from_refused() -> None:
    """A refused plugin is the framework working. Folding it into "installed" hides the reason."""
    inventory = services(
        {
            "/packs": {
                "packs": [
                    {"slug": "ok"},
                    {"slug": "bad", "status": "rejected", "rejection_reason": "elevated perms"},
                ]
            }
        }
    ).plugins.inventory()

    assert [p.slug for p in inventory.active] == ["ok"]
    assert [p.slug for p in inventory.rejected] == ["bad"]
    assert len(inventory.all) == 2


def test_categories_are_derived_from_the_inventory() -> None:
    inventory = demo().plugins.inventory()

    assert "prompt_injection" in inventory.categories
    assert "evaluation" in inventory.categories


def test_enable_and_disable_are_backend_state_changes_not_file_edits() -> None:
    """ "Do not edit plugin code": the dashboard names a slug and an action, and the backend writes
    to plugins.yaml through the PluginManager -- the one place plugin state is mutated."""
    transport = FakeTransport({"POST /packs/p/disable": {"slug": "p", "enabled": False}})

    plugin = build_services_with(transport).plugins.disable("p")

    assert not plugin.enabled
    assert transport.calls == [("POST", "/packs/p/disable")]


def test_validation_reports_each_failing_check() -> None:
    report = services(
        {
            "POST /packs/p/validate": {
                "slug": "p",
                "valid": False,
                "checks": [
                    {"name": "manifest", "passed": True},
                    {"name": "api_version", "passed": False, "detail": "2.0 is not compatible"},
                ],
            }
        }
    ).plugins.validate("p")

    assert not report.valid
    assert [c.name for c in report.failures] == ["api_version"]


def test_validity_is_inferred_when_the_backend_does_not_state_it() -> None:
    report = services(
        {"POST /packs/p/validate": {"checks": [{"name": "manifest", "passed": False}]}}
    ).plugins.validate("p")

    assert not report.valid


# -- scans -----------------------------------------------------------------------------------------


def test_a_scan_without_the_authorization_confirmation_is_refused_locally() -> None:
    """A second gate in front of the backend's own (ADR-017). Deliberately redundant: the cost is
    one boolean, and the failure it prevents is scanning something nobody agreed to."""
    with pytest.raises(DashboardError, match="authorized"):
        demo().scans.start(ScanRequest(target="vulnerable-rag", authorized=False))


def test_an_authorized_scan_starts_and_returns_an_id() -> None:
    scan_id = demo().scans.start(ScanRequest(target="vulnerable-rag", authorized=True))

    assert scan_id.startswith("scan-")


def test_a_target_with_no_authorization_record_is_refused_by_the_backend() -> None:
    """The backend's refusal is the one that matters, and it is phrased as a refusal rather than an
    error -- a refused scan is the framework working."""
    transport = FakeTransport(
        {"POST /scans": ScanRejectedError("target has no authorization record")}
    )

    with pytest.raises(ScanRejectedError):
        build_services_with(transport).scans.start(ScanRequest(target="t", authorized=True))


def test_a_scan_request_is_not_ready_without_both_a_target_and_the_confirmation() -> None:
    assert not ScanRequest(target="", authorized=True).ready
    assert not ScanRequest(target="t", authorized=False).ready
    assert ScanRequest(target="t", authorized=True).ready


def test_a_scan_that_returns_no_id_is_an_error_rather_than_a_silent_success() -> None:
    with pytest.raises(DashboardError, match="no scan id"):
        build_services_with(FakeTransport({"POST /scans": {}})).scans.start(
            ScanRequest(target="t", authorized=True)
        )


@pytest.mark.parametrize("state", ["queued", "running"])
def test_polling_continues_while_a_scan_is_live(state: str) -> None:
    assert should_poll(state)


@pytest.mark.parametrize("state", ["completed", "failed", "cancelled"])
def test_polling_stops_at_a_terminal_state(state: str) -> None:
    """A poller that keeps asking after a scan finished is a busy loop against the backend that
    nobody notices until it has run on a laptop for eight hours."""
    assert not should_poll(state)


def test_progress_degrades_to_the_scan_record_when_there_is_no_progress_route() -> None:
    """A missing live stage should not produce an error banner over a scan that is running fine."""
    transport = FakeTransport({"GET /scans/s1": {"id": "s1", "state": "running"}})

    progress = build_services_with(transport).scans.progress("s1")

    assert progress.state == "running"


def test_logs_return_empty_rather_than_failing_when_the_backend_has_no_log_route() -> None:
    """A missing log pane should not take down the progress view it sits next to."""
    assert services().scans.logs("s1") == []


def test_logs_are_capped_to_the_requested_limit() -> None:
    lines = {"lines": [{"message": f"m{i}"} for i in range(50)]}
    service = services({"/scans/s1/logs": lines}).scans

    assert len(service.logs("s1", limit=5)) == 5


def test_profiles_fall_back_to_the_shipped_three() -> None:
    """The page stays usable against an API that predates ``/profiles``."""
    assert [p.id for p in services().scans.profiles()] == ["quick", "standard", "deep"]


def test_the_estimate_scales_with_the_plugins_selected() -> None:
    """Arithmetic from something the operator can see beats a confident number derived from
    nothing."""
    service = demo().scans
    profile = ScanProfile(id="standard", estimated_cases=340)

    few, _ = service.estimate(profile, 2)
    many, _ = service.estimate(profile, 8)

    assert many > few


def test_cancelling_a_scan_reports_the_new_state() -> None:
    service = demo().scans
    scan_id = service.start(ScanRequest(target="vulnerable-rag", authorized=True))

    assert service.cancel(scan_id).state == "cancelled"


# -- reports ---------------------------------------------------------------------------------------


def test_report_formats_come_from_the_backend_not_from_a_constant() -> None:
    """PDF ships as a declared placeholder. The UI has to learn that from the engine rather than
    hardcode a guess that goes stale the moment PDF lands."""
    formats = demo().reports.formats()

    assert formats["html"] is True
    assert formats["pdf"] is False


def test_generating_an_unavailable_format_is_refused_with_the_reason() -> None:
    with pytest.raises(ReportFailureError, match="cannot render"):
        demo().reports.generate("scan-0006", "pdf")


def test_generating_an_available_format_produces_a_report() -> None:
    report = demo().reports.generate("scan-0006", "markdown")

    assert report.scan_id == "scan-0006"
    assert report.fmt == "markdown"


def test_an_empty_report_body_is_an_error_rather_than_a_blank_page() -> None:
    transport = FakeTransport({"GET /scans/s/reports/id/r": {"content": ""}})

    with pytest.raises(ReportFailureError):
        build_services_with(transport).reports.open_report("s", "r", "html")


def test_a_rendered_report_gets_a_filename_and_a_media_type() -> None:
    transport = FakeTransport({"GET /scans/s/reports/id/r": {"content": "<h1>hi</h1>"}})

    rendered = build_services_with(transport).reports.open_report("s", "r", "html")

    assert rendered.filename == "r.html"
    assert rendered.media_type == "text/html"


def test_listing_reports_is_empty_rather_than_an_error_without_the_endpoint() -> None:
    """ "No reports yet" and "this API cannot list reports" look identical to an operator, and the
    empty state already explains what to do next."""
    assert services().reports.list_reports() == []


def test_a_report_size_is_rendered_in_readable_units() -> None:
    assert ReportView(id="r", size_bytes=512).size_label == "512 B"
    assert ReportView(id="r", size_bytes=2048).size_label == "2.0 KB"
    assert ReportView(id="r", size_bytes=3_145_728).size_label == "3.0 MB"


def test_deleting_a_report_removes_it() -> None:
    service = demo().reports
    before = len(service.list_reports())

    service.delete_report("rep-0001")

    assert len(service.list_reports()) == before - 1


# -- history ---------------------------------------------------------------------------------------


def test_history_is_returned_newest_first() -> None:
    """A table is read top down. An unstable order makes the page appear to shuffle on every poll."""
    scans = demo().history.list_scans()

    assert [s.id for s in scans] == sorted((s.id for s in scans), reverse=True)


def test_a_trend_is_returned_oldest_first() -> None:
    """A trend line is read left to right. The reversal happens once, in the service, so no chart
    has to remember to do it."""
    points = demo().history.trend("vulnerable-rag")

    assert [when for when, _ in points] == sorted(when for when, _ in points)


def test_comparison_is_a_backend_call() -> None:
    """Finding identity is the analyzer's rule, and cross-version comparison is refused rather than
    approximated (ADR-011). Computing it here would produce a second, subtly wrong answer."""
    comparison = demo().history.compare("scan-0001", "scan-0006")

    assert comparison.comparable
    assert comparison.risk_delta == pytest.approx(6.0)


def test_comparison_says_so_when_the_backend_cannot_do_it() -> None:
    transport = FakeTransport(
        {"/scans/scan-1": {"id": "scan-1"}, "/scans/scan-2": {"id": "scan-2"}}
    )

    comparison = build_services_with(transport).history.compare("scan-1", "scan-2")

    assert not comparison.comparable
    assert comparison.reason


# -- status ----------------------------------------------------------------------------------------


def test_every_named_subsystem_gets_a_row_even_when_the_backend_omits_it() -> None:
    """A subsystem that quietly vanishes from the page reads as healthy and means the opposite."""
    status = services({"/health": {"components": {"sqlite": {"status": "ok"}}}}).status.status()

    assert len(status.components) == len(SUBSYSTEMS)
    assert {c.status for c in status.components} == {"ok", "unknown"}


def test_the_eight_subsystems_the_brief_names_are_all_present() -> None:
    labels = {label for _, label in SUBSYSTEMS}

    assert labels == {
        "FastAPI",
        "Ollama",
        "SQLite",
        "ChromaDB",
        "Analyzer",
        "Reporting Engine",
        "Plugin Framework",
        "SDK",
    }


def test_overall_health_is_worst_wins() -> None:
    status = demo().status.status()

    assert status.overall == "degraded"  # the pdf renderer placeholder


def test_a_disabled_subsystem_is_not_a_degradation() -> None:
    """Something switched off on purpose is not a fault."""
    from ragstrike.dashboard.services.models import ComponentHealth

    status = SystemStatus(
        components=(
            ComponentHealth("SQLite", "ok"),
            ComponentHealth("Ollama", "disabled"),
        )
    )

    assert status.overall == "ok"


def test_an_unreachable_backend_reports_unknown_rather_than_healthy() -> None:
    status = services({"/health": BackendUnavailableError("refused")}).status.status()

    assert status.overall == "unknown"


def test_the_reachability_probe_never_raises() -> None:
    """Every page asks this before anything else. If it could throw, one clear "backend offline"
    would become nine separate crashes."""

    class Exploding:
        name = "boom"

        def request(self, *_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("socket exploded")

        def describe(self) -> str:
            return "boom"

        def close(self) -> None:
            return None

    assert StatusService(Exploding()).reachable() is False  # type: ignore[arg-type]  # deliberate stub


def test_resources_report_unavailable_rather_than_zero() -> None:
    """Zero CPU and a healthy-looking bar is worse than admitting the number is missing."""
    status = services({"/health": {"components": {}}}).status.status()

    assert not status.resources.available


# -- settings --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    ["api_key", "OLLAMA_API_KEY", "db.password", "headers.Authorization", "session_cookie"],
)
def test_sensitive_keys_are_recognised_by_name(key: str) -> None:
    """Name matching rather than an allowlist of known fields: a backend that starts returning
    ``ollama_api_key`` tomorrow is redacted today."""
    assert is_sensitive(key)


@pytest.mark.parametrize("key", ["api_base_url", "theme", "refresh_interval_s"])
def test_ordinary_keys_are_not_redacted(key: str) -> None:
    assert not is_sensitive(key)


def test_redaction_reaches_nested_structures() -> None:
    cleaned = redact({"engine": {"providers": [{"name": "ollama", "api_key": "sk-real"}]}})

    assert "sk-real" not in str(cleaned)


def test_the_effective_configuration_is_redacted_before_it_is_displayed() -> None:
    config = DashboardConfig()

    rendered = services().settings.effective_config(config)

    assert rendered["theme"] == "dark"
    assert "reports" in rendered


def test_applying_an_unknown_preference_key_does_not_discard_the_known_ones() -> None:
    """The settings form posts whatever widgets it rendered. A stale key from a previous version
    should not stop the other seven settings saving."""
    updated = SettingsService.apply(
        DashboardConfig(), {"theme": "light", "no_such_setting": "value"}
    )

    assert updated.theme == "light"


def test_the_dashboard_no_longer_asks_the_backend_for_its_configuration() -> None:
    """``engine_config`` was removed along with the panel that displayed it.

    It existed only to call ``GET /config``, which the API does not serve. Implementing that route
    would have published the engine's safety policy and paths over an unauthenticated API, so the
    caller was deleted instead of the gap being filled.
    """
    assert not hasattr(services().settings, "engine_config")



def test_an_unknown_code_shows_the_backend_message_rather_than_inventing_one() -> None:
    error = from_envelope(400, {"error": {"code": "brand_new", "message": "explain yourself"}})

    assert isinstance(error, BackendRequestError)
    assert error.message == "explain yourself"


def test_a_non_json_error_body_still_produces_a_usable_error() -> None:
    """A proxy returning an HTML error page must not cause a parse failure on top of the original
    failure."""
    error = from_envelope(502, "<html>Bad Gateway</html>")

    assert isinstance(error, BackendRequestError)
    assert "502" in error.message


def test_the_correlation_id_survives_into_the_detail() -> None:
    """It is the only handle a user has when filing a bug against a backend they cannot read the
    logs of."""
    error = from_envelope(500, {"error": {"code": "x", "message": "m", "correlation_id": "abc123"}})

    assert "abc123" in error.detail


def test_every_error_class_offers_a_remedy() -> None:
    """A failure with no next step is a dead end. Enforced here rather than by review."""
    classes = [
        BackendUnavailableError,
        NotImplementedByBackendError,
        BackendRequestError,
        TargetMissingError,
        PluginFailureError,
        DatabaseFailureError,
        ReportFailureError,
        ConfigurationProblemError,
        ScanRejectedError,
    ]

    assert all(cls().friendly().remedy for cls in classes)


def test_a_refused_scan_is_a_warning_not_an_error() -> None:
    """Phrasing the framework working correctly as an error trains operators to click past the one
    message that exists to stop them testing something they are not authorized to test."""
    assert ScanRejectedError().friendly().severity == "warning"


def test_a_not_yet_implemented_endpoint_is_informational() -> None:
    assert NotImplementedByBackendError().friendly().severity == "info"


# -- transports ------------------------------------------------------------------------------------


def test_http_is_the_default_transport() -> None:
    """Demo mode is never inferred. An operator gets sample data only by asking for it by name."""
    assert build_transport(DashboardConfig()).name == "http"


def test_demo_mode_requires_asking_for_it() -> None:
    assert build_transport(DashboardConfig(transport="demo")).name == "demo"


def test_the_http_transport_targets_the_configured_base_url() -> None:
    transport = HttpTransport("http://127.0.0.1:8000/api/v1/")

    assert transport.describe() == "http://127.0.0.1:8000/api/v1"


def test_an_unmounted_route_is_reported_as_not_implemented_rather_than_offline() -> None:
    """Different operator action: there is nothing to restart, the capability is simply absent."""
    with pytest.raises(NotImplementedByBackendError):
        DemoTransport().request("GET", "/nothing-here")


def test_the_demo_transport_is_deterministic() -> None:
    """Demo data that changes between runs makes a layout review impossible."""
    first = DemoTransport().request("GET", "/scans")
    second = DemoTransport().request("GET", "/scans")

    assert first == second


def test_the_service_container_reports_demo_mode() -> None:
    """The banner that says "none of this is real" keys off this."""
    assert demo().is_demo
    assert not services().is_demo


def test_the_container_exposes_the_seven_services_the_brief_names() -> None:
    container = services()

    for name in ("scans", "plugins", "targets", "reports", "settings", "status", "history"):
        assert hasattr(container, name), f"missing {name}"


def test_every_service_shares_one_transport() -> None:
    """Seven clients would be seven connection pools and seven chances to point at different hosts."""
    container = services()

    assert {
        container.scans.transport,
        container.plugins.transport,
        container.targets.transport,
        container.reports.transport,
        container.settings.transport,
        container.status.transport,
        container.history.transport,
    } == {container.transport}


def test_report_service_works_without_a_backend_that_lists_formats() -> None:
    assert ReportService(FakeTransport()).formats() == {}
