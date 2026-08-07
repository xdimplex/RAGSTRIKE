"""Health, version, and profiles.

WHY HEALTH REPORTS PER COMPONENT
    "The API is up" is nearly useless for this system. The interesting failures are a database that
    cannot be opened, a plugin directory that discovers nothing, and a reporting engine missing a
    renderer -- each of which leaves the API answering 200 while the product does not work.

    So health enumerates components, and the top-level ``status`` is ``degraded`` unless every one of
    them is ``ok``. A monitor watching one boolean still learns something true.
"""

from __future__ import annotations

from datetime import UTC, datetime
import os
from typing import Annotated

from fastapi import APIRouter, Depends
import httpx

from ragstrike import PLUGIN_API_VERSION, __version__
from ragstrike.analyzers.config import build_engine as build_analyzer
from ragstrike.api.deps import get_service
from ragstrike.api.schemas.models import (
    ComponentHealth,
    HealthResponse,
    ProfileList,
    ProfileOut,
    VersionResponse,
)
from ragstrike.api.service import ScanService
from ragstrike.reporters.config import build_service as build_reporting

router = APIRouter(tags=["system"])

Service = Annotated[ScanService, Depends(get_service)]

OK = "ok"
DEGRADED = "degraded"
DOWN = "down"
#: Off by design, not broken. The dashboard excludes this from the worst-wins overall status, so a
#: subsystem RAGStrike genuinely does not use cannot drag the whole page to "degraded".
DISABLED = "disabled"


@router.get("/health", response_model=HealthResponse, summary="Per-component health")
async def health(service: Service) -> HealthResponse:
    """Report the EIGHT subsystems the SDD and the System Status page name.

    THE KEYS ARE A CONTRACT, NOT A CONVENIENCE
        This used to return four components keyed ``database``/``plugins``/``reporting``/``scans``,
        while the dashboard renders a fixed list keyed ``fastapi``/``ollama``/``sqlite``/
        ``chromadb``/``analyzer``/``reporting``/``plugin_framework``/``sdk``. Only ``reporting``
        matched. The other seven rendered as ``unknown``, which makes the page's worst-wins overall
        status ``unknown`` too -- so System Status greeted every operator with "Subsystem health
        could not be determined" no matter how healthy the system actually was.

        The dashboard's list came from the brief. The API's did not. So the API is the side that
        moves.

    ``chromadb`` is reported ``disabled`` rather than omitted: RAGStrike is the scanner and owns no
    vector store -- the labs do. Silence would render as ``unknown``, which claims a failure to
    measure where there is nothing to measure.
    """
    components = {
        # If this handler is executing, the HTTP layer is up. Saying so explicitly is what stops the
        # row rendering as `unknown`.
        "fastapi": ComponentHealth(
            status=OK, detail=f"{service.in_flight()} scans in flight", version=__version__
        ),
        "ollama": _ollama_health(),
        "sqlite": await _database_health(service),
        "chromadb": ComponentHealth(
            status=DISABLED, detail="not used by the scanner; the lab targets own the vector store"
        ),
        "analyzer": _analyzer_health(),
        "reporting": _reporting_health(),
        "plugin_framework": _plugin_health(service),
        "sdk": ComponentHealth(status=OK, detail="plugin API", version=PLUGIN_API_VERSION),
    }
    live = [c.status for c in components.values() if c.status != DISABLED]
    overall = OK if all(status == OK for status in live) else DEGRADED
    return HealthResponse(status=overall, components=components, checked_at=datetime.now(UTC))


def _analyzer_health() -> ComponentHealth:
    """The analyzer is in-process, so this checks it imports and exposes a scoring model version."""
    try:
        _, report = build_analyzer()
    except Exception as exc:  # pragma: no cover - configuration failure
        return ComponentHealth(status=DOWN, detail=f"{type(exc).__name__}: {exc}")
    # A config file that silently fell back to defaults is a degradation worth surfacing: the
    # operator's tuning is not in effect and nothing else would say so.
    missing = list(getattr(report, "missing", ()))
    if missing:
        return ComponentHealth(
            status=DEGRADED, detail=f"defaults in use for: {', '.join(missing)}", version="1.0.0"
        )
    return ComponentHealth(status=OK, detail="rules and scoring loaded", version="1.0.0")


def _ollama_health() -> ComponentHealth:
    """Whether a local Ollama is reachable.

    The scanner does not require one -- attack payloads are static data (ADR-016) and the targets do
    their own inference. It is reported because the operator is running the labs against Ollama on
    the same machine, and "the model runtime died" is the failure most likely to make every scan
    time out at once. Absent is ``disabled``, not ``down``: nothing here is broken without it.
    """
    base_url = os.environ.get("RAGSTRIKE_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=2.0)
        response.raise_for_status()
    except Exception:
        return ComponentHealth(status=DISABLED, detail=f"no local runtime at {base_url}")
    models = [m.get("name", "") for m in response.json().get("models", [])]
    return ComponentHealth(status=OK, detail=f"{len(models)} models available")


async def _database_health(service: ScanService) -> ComponentHealth:
    healthy, detail = await service.database.healthy()
    return ComponentHealth(status=OK if healthy else DOWN, detail=detail)


def _plugin_health(service: ScanService) -> ComponentHealth:
    found = service.registry.discover()
    # Refused packs are degraded, not down: the framework is working correctly and telling you a
    # pack is not. Reporting that as `ok` would hide the coverage gap it creates.
    status = OK if not found.rejected else DEGRADED
    return ComponentHealth(
        status=status,
        detail=f"{len(found.active)} active, {len(found.rejected)} refused",
        version=PLUGIN_API_VERSION,
    )


def _reporting_health() -> ComponentHealth:
    try:
        service, _, _ = build_reporting()
    except Exception as exc:  # pragma: no cover - configuration failure
        return ComponentHealth(status=DOWN, detail=f"{type(exc).__name__}: {exc}")
    formats = service.engine.formats()
    missing = sorted(name for name, available in formats.items() if not available)
    if missing:
        return ComponentHealth(status=DEGRADED, detail=f"unavailable: {', '.join(missing)}")
    return ComponentHealth(status=OK, detail=f"{len(formats)} formats")


@router.get("/version", response_model=VersionResponse, summary="Engine and contract versions")
def version() -> VersionResponse:
    service, _, _ = build_reporting()
    return VersionResponse(
        engine=__version__,
        plugin_api=PLUGIN_API_VERSION,
        scoring_model="1.0.0",
        report_formats=service.engine.formats(),
    )


@router.get("/profiles", response_model=ProfileList, summary="Available scan depths")
def profiles(service: Service) -> ProfileList:
    return ProfileList(
        profiles=[
            ProfileOut(
                id=profile.id,
                name=profile.name or profile.id,
                description=profile.description,
                packs=profile.packs,
                payload_tiers=profile.payload_tiers,
                attempts=profile.attempts,
            )
            for profile in service.profiles()
        ]
    )
