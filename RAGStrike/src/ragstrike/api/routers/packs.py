"""Attack and evaluation packs.

Refused packs are returned alongside active ones rather than filtered out. A pack that failed
compatibility is a **coverage gap**, and a listing that silently omitted it would let an operator
believe a category was tested when nothing ran (ADR-020).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ragstrike.api.deps import get_service
from ragstrike.api.schemas.models import PackList, PackOut
from ragstrike.api.service import ScanService

router = APIRouter(prefix="/packs", tags=["packs"])

Service = Annotated[ScanService, Depends(get_service)]


@router.get("", response_model=PackList, summary="Installed packs, active and refused")
def list_packs(service: Service) -> PackList:
    found = service.registry.discover()
    return PackList(
        packs=[
            PackOut(
                slug=plugin.slug,
                name=plugin.metadata().name,
                version=plugin.version,
                category=plugin.metadata().category,
                severity=str(plugin.metadata().severity),
                enabled=True,
                requires=[c.value for c in plugin.metadata().requires_capabilities],
            )
            for plugin in found.active
        ],
        refused=[
            {"slug": rejected.slug, "reason": rejected.reason, "detail": rejected.detail}
            for rejected in found.rejected
        ],
    )


@router.get("/{slug}", response_model=PackOut, summary="One pack")
def get_pack(slug: str, service: Service) -> PackOut:
    info = service.manager.info(slug)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"No pack named {slug!r}."
        )
    summary = info.summary
    return PackOut(
        slug=summary.slug,
        name=summary.name,
        version=summary.version,
        category=summary.category,
        severity=str(summary.severity),
        enabled=summary.enabled,
        requires=list(info.requires_capabilities),
    )


@router.post("/reload", response_model=PackList, summary="Force re-discovery")
def reload_packs(service: Service) -> PackList:
    """Re-read manifests and runtime configuration.

    Modules are **not** re-imported: Python caches them, and evicting third-party code from the
    cache is how two versions of one class end up in memory at once.
    """
    service.manager.reload()
    return list_packs(service)
