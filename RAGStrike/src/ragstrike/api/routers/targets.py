"""Targets: read and verify.

WHY THERE IS NO POST, PATCH, OR DELETE
    ``configs/targets.yaml`` is the single source of truth for what may be scanned, and a target
    entry carries an authorization record naming who approved testing it (ADR-017). Letting an
    unauthenticated local HTTP call add one would make the authorization record self-issued, which
    is the same as not having one.

    It would also split the source of truth: a target in the database and a target in the file, with
    no rule for which wins.

    So the API reads targets and probes them. Creating one is a deliberate act with a file edit and
    a diff -- which is what an authorization record is supposed to be evidence of. The dashboard
    handles the 501 by explaining where to add a target, which is more useful than a form that
    quietly creates an unreviewed one.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ragstrike.api.deps import get_service
from ragstrike.api.schemas.models import (
    AuthorizationOut,
    TargetList,
    TargetOut,
    VerifyResponse,
)
from ragstrike.api.service import ScanService
from ragstrike.core.config.loader import load_settings, select_target
from ragstrike.models.entities.target import Target
from ragstrike.target_adapters.registry import build_adapter

router = APIRouter(prefix="/targets", tags=["targets"])

Service = Annotated[ScanService, Depends(get_service)]


def _to_out(target: Target) -> TargetOut:
    auth = target.authorization
    return TargetOut(
        name=target.name,
        adapter=target.adapter,
        url=target.url,
        timeout_s=target.timeout_s,
        enabled=target.enabled,
        authorized=target.is_authorized,
        authorization=(
            AuthorizationOut(
                authorized_by=auth.authorized_by,
                authorization_ref=auth.authorization_ref,
                scope=auth.scope,
            )
            if auth
            else None
        ),
        capabilities=[c.value for c in target.capabilities],
    )


@router.get("", response_model=TargetList, summary="Configured targets")
def list_targets(service: Service) -> TargetList:
    return TargetList(targets=[_to_out(t) for t in service.configured_targets()])


@router.get("/{name}", response_model=TargetOut, summary="One target")
def get_target(name: str, service: Service) -> TargetOut:
    # `select_target` raises TargetNotFoundError, which the error handler renders as a 404 with the
    # list of names that do exist -- the same message the CLI gives.
    return _to_out(select_target(service.configured_targets(), name))


@router.post("/{name}/verify", response_model=VerifyResponse, summary="Probe a target")
async def verify_target(name: str, service: Service) -> VerifyResponse:
    target = select_target(service.configured_targets(), name)
    settings = load_settings()

    # The scope check lives inside build_adapter, so verify cannot become a way to reach a host that
    # scan would refuse. That exact bypass existed once, through `targets --verify`, and was closed
    # in Phase 6 by moving the guard to this chokepoint.
    adapter = build_adapter(
        target,
        allow_remote=settings.safety.allow_remote_targets,
        allowed_hosts=settings.safety.allowed_hosts,
        retry=settings.engine.retry,
    )
    try:
        result = await adapter.health_check()
    finally:
        await adapter.close()

    return VerifyResponse(
        name=target.name,
        reachable=result.reachable,
        latency_ms=result.latency_ms,
        detail=result.detail,
    )


_NOT_SUPPORTED = (
    "Targets are declared in configs/targets.yaml, not over HTTP. A target carries an "
    "authorization record naming who approved testing it; one created by an unauthenticated "
    "local call would be self-issued."
)


def _refuse_write() -> None:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_SUPPORTED)


@router.post("", summary="Not supported -- targets are declared in configuration")
def create_target() -> None:
    """Refused, deliberately. See the module docstring."""
    _refuse_write()


@router.patch("/{name}", summary="Not supported -- targets are declared in configuration")
def update_target(name: str) -> None:  # noqa: ARG001 - path param, required for routing
    """Refused, deliberately. See the module docstring."""
    _refuse_write()


@router.delete("/{name}", summary="Not supported -- targets are declared in configuration")
def delete_target(name: str) -> None:  # noqa: ARG001 - path param, required for routing
    """Refused, deliberately. See the module docstring."""
    _refuse_write()
