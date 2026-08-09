"""Attack and evaluation packs.

Refused packs are returned alongside active ones rather than filtered out. A pack that failed
compatibility is a **coverage gap**, and a listing that silently omitted it would let an operator
believe a category was tested when nothing ran (ADR-020).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from ragstrike.api.deps import get_service
from ragstrike.api.schemas.models import (
    PackCheckOut,
    PackList,
    PackOut,
    PackValidationOut,
)
from ragstrike.api.service import ScanService
from ragstrike.plugins.registry.validator import validate_structure

log = logging.getLogger(__name__)

router = APIRouter(prefix="/packs", tags=["packs"])

Service = Annotated[ScanService, Depends(get_service)]


def _payloads(plugin: Any) -> int:
    """How many payloads *plugin* will send, or 0 if it will not say.

    Calls the plugin's own ``payloads()`` -- the very method the scheduler calls -- so the number
    the UI shows is the number that will run, not a per-plugin constant. It is cheap: enumerating
    every installed pack takes about thirty milliseconds, because payload files are small and the
    contract requires the method to be deterministic and side-effect free.

    A plugin that raises is reported as 0 rather than taking the listing down with it. Third-party
    packs run here, and one malformed payload file must not be able to blank the Plugins page --
    that is the same reasoning that makes a refused pack visible instead of hidden.
    """
    try:
        return len(plugin.attack.payloads())
    except Exception:  # third-party plugin code: any failure here is the plugin's, not the API's
        log.warning("pack could not enumerate payloads", extra={"slug": plugin.slug})
        return 0


def _payload_count(service: ScanService, slug: str) -> int:
    """:func:`_payloads` for one slug, looked up among the active packs.

    ``PluginManager.info`` returns metadata without the attack instance, so the count cannot come
    from there. A disabled pack is not active and reports 0, which is the truthful answer: it will
    send nothing until it is enabled.
    """
    for plugin in service.manager.health().active:
        if plugin.slug == slug:
            return _payloads(plugin)
    return 0


def _installed(service: ScanService, slug: str) -> bool:
    """Is *slug* installed at all -- active, disabled, or refused?

    `PluginManager.info` answers "is it ACTIVE", which is a different question and the wrong one for
    enable/disable: the moment a pack is disabled it leaves the active set, and a handler keyed on
    `info` then denies it exists.
    """
    health = service.manager.health()
    if any(p.slug == slug for p in health.active):
        return True
    return any(r.slug == slug for r in health.rejected)


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
                payloads=_payloads(plugin),
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
        payloads=_payload_count(service, slug),
        description=info.description,
        author=info.author,
        # Only the permissions actually GRANTED. The manager reports every permission as a
        # name -> bool pair, and listing the False ones would read as "this pack writes to the
        # filesystem" for a pack that does not.
        permissions=[name for name, granted in info.permissions.items() if granted],
        api_version=info.requires_api,
    )


@router.post(
    "/{slug}/validate",
    response_model=PackValidationOut,
    summary="Re-validate an installed pack",
)
def validate_pack(slug: str, service: Service) -> PackValidationOut:
    """Run the framework's own validation rules against one installed pack.

    WHY THIS ROUTE EXISTS
        The dashboard's Plugins page has offered a "Validate" button since Phase 12. It called
        ``POST /packs/{slug}/validate``, which was never implemented, so every click on every pack
        returned 404 and rendered as "request rejected". The button worked exactly as designed and
        the server had nothing to answer with.

    WHY VALIDATION IS RE-RUN RATHER THAN CACHED
        The registry validates at load time and a failing pack never becomes active. That answers
        "was it valid when loaded?"; this answers "is it valid now?" -- after a manifest edit, a
        payload file change, or a config change. Those are exactly the moments an operator presses
        the button, and a cached verdict would answer the wrong question.

    READ-ONLY. It imports nothing new and mutates nothing: a validation that could change state
    would be a strange thing to offer beside a "do not edit plugin code" guarantee.
    """
    info = service.manager.info(slug)
    if info is None:
        # A DISABLED pack is not active, and validating one is a perfectly reasonable thing to want
        # to do before turning it back on.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No pack named {slug!r}, or it is disabled. Enable it to validate it."
                if _installed(service, slug)
                else f"No pack named {slug!r}."
            ),
        )

    # `manifest_path`, not a directory: `PluginInfo` carries the path to the manifest file, and the
    # structure validator wants the directory that contains it.
    report = validate_structure(Path(info.manifest_path).parent)

    return PackValidationOut(
        slug=slug,
        valid=report.valid,
        checks=[
            PackCheckOut(name=check.rule, passed=check.passed, detail=check.detail)
            for check in report.checks
        ],
    )


# REGISTERED AFTER `/{slug}/validate`, AND THAT ORDER IS LOAD-BEARING.
#
# FastAPI matches routes in registration order, so a generic `/{slug}/{action}` declared first
# swallows `/{slug}/validate` -- `action` binds to "validate" and the handler rejects it as an
# unknown action. Adding this route above the specific one turned a working endpoint into a 404,
# which is exactly the bug it was written to fix, moved one door along.


@router.post("/{slug}/{action}", response_model=PackOut, summary="Enable or disable a pack")
def toggle_pack(slug: str, action: str, service: Service) -> PackOut:
    """Turn a pack on or off by writing to ``configs/plugins.yaml``.

    WHY THIS ROUTE EXISTS
        The dashboard's Enable/Disable buttons have called ``POST /packs/{slug}/{action}`` since
        Phase 12. The route was never implemented, so every click returned 404 and surfaced as
        "request rejected" -- the same shape as the Validate button, and found the same way.

        ``PluginManager.enable``/``disable`` already did the work; only the HTTP door was missing.

    WHY A WRITE TO plugins.yaml AND NOT AN IN-MEMORY FLAG
        The registry re-reads that file, so the change survives a restart and is visible to the CLI
        and to anyone reading the repository. An in-memory toggle would make the dashboard and the
        CLI disagree about which packs are live, and the scan report would cite whichever the engine
        happened to believe.
    """
    if action not in ("enable", "disable"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown pack action {action!r}. Use 'enable' or 'disable'.",
        )
    # `_installed` and NOT `manager.info`, which only sees ACTIVE packs.
    #
    # Disabling a pack removes it from the active set, so a second call -- to re-enable it, or to
    # validate it -- found nothing and answered 404. Disable was a one-way door: the button turned a
    # pack off and then denied the pack existed.
    if not _installed(service, slug):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"No pack named {slug!r}."
        )

    written = (
        service.manager.enable(slug) if action == "enable" else service.manager.disable(slug)
    )
    if not written:
        # `False` means there was no plugins.yaml to write to. Saying so beats a silent success that
        # leaves the button looking broken on the next render.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No configs/plugins.yaml to write to, so the change could not be persisted. "
                "Create the file, or edit it directly."
            ),
        )

    # A just-disabled pack is no longer active, so its metadata may be unavailable. Report the state
    # that is certainly true rather than 404-ing on the call that just succeeded.
    info = service.manager.info(slug)
    if info is None:
        return PackOut(
            slug=slug,
            name=slug,
            version="",
            category="",
            severity="",
            enabled=(action == "enable"),
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
        payloads=_payload_count(service, slug),
        description=info.description,
        author=info.author,
        # Only the permissions actually GRANTED. The manager reports every permission as a
        # name -> bool pair, and listing the False ones would read as "this pack writes to the
        # filesystem" for a pack that does not.
        permissions=[name for name, granted in info.permissions.items() if granted],
        api_version=info.requires_api,
    )


@router.post("/reload", response_model=PackList, summary="Force re-discovery")
def reload_packs(service: Service) -> PackList:
    """Re-read manifests and runtime configuration.

    Modules are **not** re-imported: Python caches them, and evicting third-party code from the
    cache is how two versions of one class end up in memory at once.
    """
    service.manager.reload()
    return list_packs(service)
