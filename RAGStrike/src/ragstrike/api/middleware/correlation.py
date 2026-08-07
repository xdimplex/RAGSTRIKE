"""Correlation ids and request logging.

WHY EVERY REQUEST GETS AN ID
    An error envelope that says "an unexpected error occurred" is useless on its own. It is useful
    when it also carries an id the operator can grep for in the log, where the real traceback is.
    That is the whole trade: the browser gets a message that leaks nothing, the operator gets the
    detail, and the id is the join.

    A client may supply its own ``X-Correlation-ID``. It is length-capped and stripped of anything
    non-printable before use -- an id taken verbatim from a request and written into a log file is a
    log-injection vector, and this is a security tool.

WHAT IS NOT LOGGED
    Query strings and request bodies. The same rule that governs the scanner's own logs applies to
    its API: a prompt or a document fragment must not reach a log line. Method, path template,
    status, and duration are enough to operate on.
"""

from __future__ import annotations

import logging
import time
from typing import Any
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

log = logging.getLogger(__name__)

HEADER = "X-Correlation-ID"

#: Long enough for a UUID or a trace id, short enough that nobody can push a paragraph into the log.
_MAX_LENGTH = 64


def _clean(value: str) -> str:
    """Keep printable ASCII, drop everything else, and cap the length.

    Newlines are the reason this exists: a supplied id containing ``\\n`` would let a caller forge
    additional log records.
    """
    return "".join(c for c in value if c.isascii() and c.isprintable())[:_MAX_LENGTH]


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Attach a correlation id to every request, and log the outcome."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied = _clean(request.headers.get(HEADER, ""))
        correlation_id = supplied or uuid.uuid4().hex
        request.state.correlation_id = correlation_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Logged here because the exception handler sees a sanitised message; this is the only
            # place with the traceback and the timing together.
            log.exception(
                "request failed",
                extra=_fields(request, correlation_id, started, status=500),
            )
            raise

        log.info(
            "request",
            extra=_fields(request, correlation_id, started, status=response.status_code),
        )
        response.headers[HEADER] = correlation_id
        return response


def _fields(
    request: Request, correlation_id: str, started: float, *, status: int
) -> dict[str, Any]:
    # `route.path` is the *template* (`/scans/{scan_id}`), not the concrete path. Logging the
    # template keeps identifiers out of the log and makes the records aggregatable.
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    return {
        "correlation_id": correlation_id,
        "method": request.method,
        "path": path,
        "status": status,
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }


__all__ = ["HEADER", "CorrelationMiddleware"]
