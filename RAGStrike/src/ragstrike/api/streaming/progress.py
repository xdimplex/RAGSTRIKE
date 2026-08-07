"""Server-sent events for scan progress.

WHY SSE AND NOT WEBSOCKETS (ADR-014)
    Progress is one-directional: the server talks, the client listens. SSE is plain HTTP, survives
    proxies that mangle upgrades, reconnects on its own, and needs no framing protocol. A WebSocket
    would buy bidirectionality nobody needs and cost a second transport to test.

WHY THE STREAM ALWAYS TERMINATES
    Every stream ends with a ``done`` event and closes -- on completion, on failure, on cancellation,
    and on the client disconnecting. A progress stream that stays open after its scan has finished is
    a leaked task and a browser connection held forever.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from ragstrike.api.deps import get_service
from ragstrike.api.service import ScanService

log = logging.getLogger(__name__)

router = APIRouter(prefix="/scans", tags=["scans"])

#: How often a snapshot is emitted while a scan runs.
_INTERVAL_S = 1.0

#: Emitted when nothing has changed, so proxies and load balancers do not time the connection out.
_KEEPALIVE = ": keepalive\n\n"


def _event(name: str, payload: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload)}\n\n"


@router.get(
    "/{scan_id}/events",
    summary="Stream scan progress (SSE)",
    response_class=StreamingResponse,
)
async def stream_progress(
    scan_id: str,
    request: Request,
    service: ScanService = Depends(get_service),  # noqa: B008 - FastAPI dependency injection
) -> StreamingResponse:
    running = service.running(scan_id)
    if running is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan {scan_id!r} is not running. Use /progress for a finished scan.",
        )

    async def stream() -> AsyncIterator[str]:
        last: dict[str, Any] | None = None
        try:
            while True:
                # Checked every tick: a browser tab closing must stop the loop, not leave it
                # polling a scan nobody is watching until the process exits.
                if await request.is_disconnected():
                    log.debug("progress client disconnected", extra={"scan_id": scan_id})
                    return

                snapshot = running.snapshot()
                if snapshot != last:
                    yield _event("progress", snapshot)
                    last = snapshot
                else:
                    yield _KEEPALIVE

                if running.finished.is_set():
                    yield _event(
                        "done",
                        {**running.snapshot(), "error": running.error},
                    )
                    return

                try:
                    await asyncio.wait_for(running.finished.wait(), timeout=_INTERVAL_S)
                except TimeoutError:
                    continue
        except asyncio.CancelledError:  # pragma: no cover - server shutdown
            raise

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Nginx buffers proxied responses by default, which holds every event until the scan
            # ends and turns a live stream into one delivery at the end.
            "X-Accel-Buffering": "no",
        },
    )
