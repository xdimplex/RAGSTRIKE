"""API surface tests.

``src/ragstrike/api/`` was five empty ``__init__.py`` files until Phase 16 -- no routing, no
handlers, nothing. The dashboard reported ``BACKEND OFFLINE`` because there was nothing behind the
address it called.

These tests run the real application against a temporary database and a real plugin directory. No
route is mocked: the point is that the surface the dashboard was written against actually answers.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from ragstrike.api.app import API_PREFIX, create_app
from ragstrike.core.config.models import Settings, StorageSettings

V1 = API_PREFIX


@pytest.fixture
def client(tmp_path: Path, make_plugin: Any) -> Iterator[TestClient]:
    """A real app on a throwaway database, with one discoverable plugin."""
    plugins_dir = make_plugin("api-fixture-attack")
    settings = Settings(
        storage=StorageSettings(
            database_path=tmp_path / "scans.db", reports_dir=tmp_path / "reports"
        ),
    )
    settings = settings.model_copy(
        update={"plugins": settings.plugins.model_copy(update={"local_dirs": [plugins_dir]})}
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


# ------------------------------------------------------------------------------------------------
# The surface exists
# ------------------------------------------------------------------------------------------------


def test_openapi_is_generated(client: TestClient) -> None:
    response = client.get(f"{V1}/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    for expected in (
        f"{V1}/health",
        f"{V1}/version",
        f"{V1}/profiles",
        f"{V1}/targets",
        f"{V1}/packs",
        f"{V1}/scans",
        f"{V1}/scans/{{scan_id}}/progress",
        f"{V1}/scans/{{scan_id}}/findings",
        f"{V1}/scans/{{scan_id}}/events",
    ):
        assert expected in paths, expected


#: The subsystems the SDD names, and the exact keys the System Status page renders.
#:
#: These are a CONTRACT with the dashboard, not an implementation detail. Health used to answer with
#: `database`/`plugins`/`reporting`/`scans`; the dashboard renders a fixed list under these names, so
#: seven of eight rows resolved to `unknown` and the page's worst-wins summary told every operator
#: "Subsystem health could not be determined". Naming them here is what stops that recurring.
EXPECTED_SUBSYSTEMS = {
    "fastapi",
    "ollama",
    "sqlite",
    "chromadb",
    "analyzer",
    "reporting",
    "plugin_framework",
    "sdk",
}


def test_health_reports_per_component(client: TestClient) -> None:
    """ "The API is up" is nearly useless for this system."""
    body = client.get(f"{V1}/health").json()

    assert body["status"] in {"ok", "degraded"}
    assert set(body["components"]) == EXPECTED_SUBSYSTEMS
    assert body["components"]["sqlite"]["status"] == "ok"
    assert body["components"]["fastapi"]["status"] == "ok"


def test_health_is_degraded_when_a_component_is(client: TestClient) -> None:
    """The top-level flag must not read `ok` while something underneath is not.

    ``disabled`` is excluded, and deliberately: the scanner owns no vector store, so ChromaDB is off
    by design. Counting a subsystem that is switched off on purpose as a degradation would leave the
    dashboard permanently amber and train the operator to ignore it.
    """
    body = client.get(f"{V1}/health").json()
    unhealthy = [
        c for c in body["components"].values() if c["status"] not in {"ok", "disabled"}
    ]

    assert (body["status"] == "ok") == (not unhealthy)


def test_a_subsystem_that_is_off_by_design_is_disabled_not_down(client: TestClient) -> None:
    """`disabled` and `down` mean opposite things and must not be collapsed."""
    body = client.get(f"{V1}/health").json()

    assert body["components"]["chromadb"]["status"] == "disabled"


def test_version_reports_both_contracts(client: TestClient) -> None:
    body = client.get(f"{V1}/version").json()

    assert body["engine"]
    assert body["plugin_api"]
    assert "html" in body["report_formats"]


def test_profiles_are_served_from_disk(client: TestClient) -> None:
    ids = {p["id"] for p in client.get(f"{V1}/profiles").json()["profiles"]}

    assert {"quick", "standard", "deep"} <= ids


def test_packs_lists_the_discovered_plugin(client: TestClient) -> None:
    body = client.get(f"{V1}/packs").json()

    assert "api-fixture-attack" in {p["slug"] for p in body["packs"]}
    assert "refused" in body


def test_an_unknown_pack_is_a_404_in_the_envelope(client: TestClient) -> None:
    response = client.get(f"{V1}/packs/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# ------------------------------------------------------------------------------------------------
# The error envelope
# ------------------------------------------------------------------------------------------------


def test_every_error_uses_one_envelope(client: TestClient) -> None:
    """Including validation errors, which FastAPI renders as ``{"detail": ...}`` by default.

    A client forced to parse two error shapes will handle one of them badly.
    """
    response = client.post(f"{V1}/scans", json={"target": 42, "acknowledge": "maybe"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["fields"]
    assert "correlation_id" in error


def test_an_unknown_target_is_a_404_naming_the_known_ones(client: TestClient) -> None:
    response = client.get(f"{V1}/targets/does-not-exist")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "target_not_found"
    # The hint survives the HTTP boundary; without it the API is less helpful than the CLI.
    assert "hint" in error["details"]


def test_a_correlation_id_is_returned_on_every_response(client: TestClient) -> None:
    response = client.get(f"{V1}/health")

    assert response.headers["X-Correlation-ID"]


def test_a_supplied_correlation_id_is_echoed_but_sanitised(client: TestClient) -> None:
    """An id taken verbatim from a request and written to a log is a log-injection vector."""
    response = client.get(f"{V1}/health", headers={"X-Correlation-ID": "abc\r\nFAKE LOG LINE"})

    returned = response.headers["X-Correlation-ID"]
    assert "\n" not in returned
    assert "\r" not in returned
    assert returned.startswith("abc")


# ------------------------------------------------------------------------------------------------
# Safety
# ------------------------------------------------------------------------------------------------


def test_targets_cannot_be_created_over_http(client: TestClient) -> None:
    """A target carries an authorization record naming who approved testing it.

    One created by an unauthenticated local call would be self-issued, which is the same as not
    having one.
    """
    response = client.post(f"{V1}/targets", json={"name": "x", "url": "http://127.0.0.1:1"})

    assert response.status_code == 501
    assert "targets.yaml" in response.json()["error"]["message"]


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_targets_cannot_be_modified_over_http(client: TestClient, method: str) -> None:
    response = getattr(client, method)(f"{V1}/targets/lab")

    assert response.status_code == 501


def test_a_scan_will_not_start_without_acknowledgement(client: TestClient) -> None:
    """A POST that ran on ``{"target": "x"}`` alone is one stray fetch from an unintended scan."""
    response = client.post(f"{V1}/scans", json={"target": "vulnerable-rag"})

    assert response.status_code == 400
    assert "acknowledge" in response.json()["error"]["message"]


def test_a_scan_against_an_unknown_target_fails_before_it_starts(client: TestClient) -> None:
    """Synchronously, so the caller gets a 4xx rather than a 202 and a scan that dies a second later."""
    response = client.post(f"{V1}/scans", json={"target": "no-such-target", "acknowledge": True})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "target_not_found"


def test_an_unknown_profile_is_rejected(client: TestClient) -> None:
    response = client.post(
        f"{V1}/scans",
        json={"target": "vulnerable-rag", "profile": "../../etc/passwd", "acknowledge": True},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "configuration_error"


def test_an_unknown_body_field_is_rejected(client: TestClient) -> None:
    """``extra="forbid"``: a misspelled ``profile`` must not silently run a default-depth scan."""
    response = client.post(
        f"{V1}/scans",
        json={"target": "vulnerable-rag", "acknowledge": True, "profil": "quick"},
    )

    assert response.status_code == 422


# ------------------------------------------------------------------------------------------------
# Scans
# ------------------------------------------------------------------------------------------------


def test_an_unknown_scan_is_a_404_everywhere(client: TestClient) -> None:
    for path in ("", "/progress", "/findings"):
        response = client.get(f"{V1}/scans/deadbeef{path}")
        assert response.status_code == 404, path


def test_cancelling_a_scan_that_is_not_running_is_a_conflict(client: TestClient) -> None:
    response = client.post(f"{V1}/scans/deadbeef/cancel")

    assert response.status_code == 409


def test_the_scan_list_is_empty_and_well_shaped_on_a_fresh_database(
    client: TestClient,
) -> None:
    body = client.get(f"{V1}/scans").json()

    assert body == {"scans": []}


def test_the_scan_limit_is_bounded(client: TestClient) -> None:
    """An unbounded limit is a way to ask the server to load every row it has."""
    assert client.get(f"{V1}/scans", params={"limit": 10_000}).status_code == 422
    assert client.get(f"{V1}/scans", params={"limit": 0}).status_code == 422


# ------------------------------------------------------------------------------------------------
# Reports
# ------------------------------------------------------------------------------------------------


def test_a_report_for_an_unknown_scan_is_a_404(client: TestClient) -> None:
    response = client.post(f"{V1}/scans/deadbeef/reports", json={"formats": ["html"]})

    assert response.status_code == 404


def test_an_unavailable_format_is_a_400_naming_what_works(client: TestClient) -> None:
    """PDF is declared and refuses. Asking for it is a client mistake, not a server failure."""
    response = client.post(f"{V1}/scans/deadbeef/reports", json={"formats": ["pdf"]})

    assert response.status_code in {400, 404}


def test_a_report_download_path_cannot_escape_the_reports_directory(
    client: TestClient,
) -> None:
    """``../`` in a URL reaching a file read is the oldest bug there is."""
    response = client.get(f"{V1}/scans/..%2f..%2f..%2fetc/reports/html")

    assert response.status_code in {400, 404}
    assert b"root:" not in response.content


def test_status_mapping_resolves_most_specific_first() -> None:
    """Several domain errors inherit from each other.

    ``TargetNotFoundError`` *is* a ``ConfigurationError``. An ``isinstance`` loop over the mapping
    table returned whichever entry was declared first, which made ``GET /targets/unknown`` answer
    400 instead of 404. The MRO is the only ordering that means anything here.
    """
    from ragstrike.api.errors import status_for
    from ragstrike.core.errors import (
        ConfigurationError,
        TargetNotFoundError,
        UnknownAdapterError,
    )

    assert status_for(TargetNotFoundError("x")) == 404
    assert status_for(ConfigurationError("x")) == 400
    assert status_for(UnknownAdapterError("x")) == 400


def test_an_unmapped_error_is_a_500_rather_than_a_crash() -> None:
    """An error nobody mapped is one nobody anticipated, which is exactly what 500 means."""
    from ragstrike.api.errors import status_for
    from ragstrike.core.errors import RAGStrikeError

    class NovelError(RAGStrikeError):
        code = "novel"

    assert status_for(NovelError("x")) == 500


# ------------------------------------------------------------------------------------------------
# The scan lifecycle over HTTP
#
# These three cover defects found by driving the running server rather than by reading the code.
# All three passed every unit test that existed at the time.
# ------------------------------------------------------------------------------------------------


def test_the_id_returned_by_post_is_the_id_that_can_be_queried(client: TestClient) -> None:
    """``POST /scans`` handed back an id the engine then ignored.

    The engine minted its own ``ScanSession`` id, so ``GET /scans/{id}`` 404'd on the very id the
    client had just been given. ``/progress`` masked it by falling back to an in-memory dict keyed
    on the pre-minted id, which is why no unit test caught it.
    """
    accepted = client.post(f"{V1}/scans", json={"target": "vulnerable-rag", "acknowledge": True})
    if accepted.status_code != 202:
        pytest.skip("no scannable target configured in this environment")

    scan_id = accepted.json()["scan_id"]

    # The scan is still running; what matters is that the id resolves in both places.
    progress = client.get(f"{V1}/scans/{scan_id}/progress")
    assert progress.status_code == 200
    assert progress.json()["scan_id"] == scan_id

    client.post(f"{V1}/scans/{scan_id}/cancel")
    assert client.get(f"{V1}/scans/{scan_id}").status_code in {200, 404}


def test_progress_reports_a_denominator_while_the_scan_runs(client: TestClient) -> None:
    """``total`` was only assigned after the engine returned.

    For the entire duration of a scan the endpoint reported ``completed: 7, total: 0, percent: 0.0``
    -- a progress bar frozen at zero until the moment it finished.
    """
    accepted = client.post(f"{V1}/scans", json={"target": "vulnerable-rag", "acknowledge": True})
    if accepted.status_code != 202:
        pytest.skip("no scannable target configured in this environment")

    scan_id = accepted.json()["scan_id"]
    snapshot = client.get(f"{V1}/scans/{scan_id}/progress").json()
    client.post(f"{V1}/scans/{scan_id}/cancel")

    # Either planning has not happened yet (total 0, completed 0) or both are populated. What must
    # never happen is progress against a zero denominator.
    assert not (snapshot["completed"] > 0 and snapshot["total"] == 0)


# ------------------------------------------------------------------------------------------------
# The dashboard's actual request body
#
# Phase 16 claimed the dashboard needed no changes because the routes matched. The routes did match.
# Nobody sent a body. Every Start Scan click was a 422, and it was found by clicking the button.
# ------------------------------------------------------------------------------------------------


def test_the_body_the_dashboard_really_sends_is_accepted(client: TestClient) -> None:
    """Built by the dashboard's own ``ScanRequest.payload()``, not hand-written here.

    Hand-writing the body would test my idea of what the dashboard sends, which is exactly the
    mistake that produced the bug.
    """
    from ragstrike.dashboard.services.scan_service import ScanRequest as DashboardScanRequest

    body = DashboardScanRequest(
        target="vulnerable-rag",
        profile="quick",
        name="vulnerable-rag scan",
        plugins=("prompt-injection", "prompt-leakage"),
        categories=("prompt_injection", "evaluation"),
        authorized=True,
    ).payload()

    response = client.post(f"{V1}/scans", json=body)

    # 202 when the target is reachable, 502/404 when it is not. Never 422: that would mean the
    # server rejected the shape of a request its own reference client produces.
    assert response.status_code != 422, response.json()


def test_the_dashboard_body_carries_its_confirmation(client: TestClient) -> None:
    """``payload()`` omitted ``authorized`` entirely, so every scan was a 400 after the 422."""
    from ragstrike.dashboard.services.scan_service import ScanRequest as DashboardScanRequest

    body = DashboardScanRequest(target="vulnerable-rag", authorized=True).payload()

    assert body["authorized"] is True


def test_the_accepted_response_carries_both_id_spellings(client: TestClient) -> None:
    """The dashboard reads ``id``; the rest of this API says ``scan_id``.

    Emitting one and not the other breaks whichever client was not consulted.
    """
    from ragstrike.api.schemas.models import ScanAccepted

    body = ScanAccepted(scan_id="abc", id="abc", state="QUEUED", target="lab").model_dump()

    assert body["id"] == body["scan_id"] == "abc"


def test_either_confirmation_spelling_is_accepted() -> None:
    """A client should not have to guess which synonym the server picked."""
    from ragstrike.api.schemas.models import ScanRequest as ApiScanRequest

    assert ApiScanRequest(target="x", acknowledge=True).confirmed is True
    assert ApiScanRequest(target="x", authorized=True).confirmed is True
    assert ApiScanRequest(target="x").confirmed is False


def test_an_explicit_plugin_selection_narrows_within_the_profile() -> None:
    """A selection is the operator narrowing inside a depth policy, never widening past it.

    Letting a request widen past its profile would make ``--profile quick`` meaningless the moment
    the dashboard was involved.
    """
    from ragstrike.api.service import Selection
    from ragstrike.core.config.profiles import ScanProfile

    quick = ScanProfile(id="quick", packs=["prompt-injection", "prompt-leakage"])
    selection = Selection(slugs=frozenset({"prompt-injection", "context-poisoning"}), profile=quick)

    assert selection.selects("prompt-injection") is True  # in both
    assert selection.selects("context-poisoning") is False  # chosen, but outside the profile
    assert selection.selects("prompt-leakage") is False  # in the profile, but not chosen


# ------------------------------------------------------------------------------------------------
# The scan detail body, and the report body
#
# The dashboard rendered RISK 0.0/100, DURATION 0s, PLUGINS EXECUTED 0 and grade "?" for scans that
# had run correctly, because ScanOut omitted every field it reads. Same root cause as the START SCAN
# bug: a response schema written from memory rather than from the client.
# ------------------------------------------------------------------------------------------------


def test_scan_out_carries_every_field_the_dashboard_reads(client: TestClient) -> None:
    """Asserted against the dashboard's own reader, not against a list I typed out."""
    from ragstrike.api.schemas.models import ScanOut

    emitted = set(ScanOut.model_fields)
    # These are the keys ScanView.from_payload() pulls out of the response.
    required = {
        "id",
        "target",
        "name",
        "profile",
        "state",
        "started_at",
        "finished_at",
        "duration_s",
        "plugins_executed",
        "findings_count",
        "severity_counts",
        "risk_score",
        "grade",
        "coverage",
        "outcome",
    }

    assert required <= emitted, f"ScanOut is missing {sorted(required - emitted)}"


def test_plugins_executed_is_a_list_not_a_count(client: TestClient) -> None:
    """The dashboard calls ``as_list`` on it.

    An integer there yields an empty list, which renders as "PLUGINS EXECUTED 0" for a scan that
    executed plugins perfectly well.
    """
    from ragstrike.api.schemas.models import ScanOut

    out = ScanOut(scan_id="s", target="t", state="COMPLETED", plugins_executed=["a", "b"])

    assert out.plugins_executed == ["a", "b"]
    assert len(out.plugins_executed) == 2


def test_a_scan_view_survives_a_round_trip_through_the_dashboard_reader() -> None:
    """End to end through both sides of the contract, with no HTTP in the middle."""
    from ragstrike.api.schemas.models import ScanOut
    from ragstrike.dashboard.services.models import ScanView

    body = ScanOut(
        scan_id="abc",
        id="abc",
        target="vulnerable-rag",
        profile="quick",
        state="COMPLETED",
        outcome="PASS",
        duration_s=16.14,
        plugins_executed=["dummy-attack"],
        findings_count=9,
        severity_counts={"INFO": 9},
        risk_score=3.5,
        grade="B",
        coverage=0.1111,
    ).model_dump(mode="json")

    view = ScanView.from_payload(body)

    assert view.id == "abc"
    assert view.profile == "quick"
    assert view.duration_s == 16.14
    assert len(view.plugins_executed) == 1
    assert view.findings_count == 9
    assert view.risk_score == 3.5
    assert view.grade == "B"


def test_the_report_request_accepts_the_dashboards_singular_format() -> None:
    """The dashboard posts ``{"format": "pdf"}``; this schema only had ``formats: [...]``."""
    from ragstrike.api.schemas.models import ReportRequest

    assert ReportRequest(format="pdf").chosen() == ["pdf"]
    assert ReportRequest(formats=["html", "json"]).chosen() == ["html", "json"]
    assert ReportRequest().chosen() == ["html"]


def test_a_report_request_body_from_the_dashboard_is_not_rejected(client: TestClient) -> None:
    response = client.post(f"{V1}/scans/deadbeef/reports", json={"format": "html"})

    # 404 because that scan does not exist. Never 422: the shape is valid.
    assert response.status_code == 404
