"""Security response headers, and the rate-limiting placeholder.

WHY A JSON API SETS BROWSER SECURITY HEADERS AT ALL
    Most of these headers instruct a browser, and most callers here are not browsers. Two are
    load-bearing anyway:

    ``X-Content-Type-Options: nosniff`` stops a browser from re-interpreting a JSON response as HTML.
    This API returns model output and document text inside JSON, which is attacker-influenced by
    construction -- content sniffing plus a crafted response body is a real XSS path.

    ``Content-Security-Policy`` matters because FastAPI serves ``/docs``, which *is* a browser page,
    and it renders schema descriptions that come from this application's own source.

    The rest are cheap and correct. A header that costs nothing and closes a class of mistake is
    worth setting even when today's callers do not need it.

WHY THE RATE LIMITER COUNTS BUT DOES NOT LIMIT
    See ``rag/policy/controls/future_controls.py``. Rate limiting keyed on source IP is meaningless
    on loopback, where every request comes from ``127.0.0.1``, and there is no authentication to key
    on instead. Rather than ship a limiter that appears to protect and does not, this middleware
    records the request counts a real limiter would need -- so the eventual control has data to be
    tuned against, and so ``GET /health`` can report the gap honestly.
"""

from __future__ import annotations

import logging
from collections import Counter

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

log = logging.getLogger(__name__)

#: Applied to every response. Values chosen for an API that also serves ``/docs``.
SECURITY_HEADERS: dict[str, str] = {
    # Never let a browser second-guess the declared content type.
    "X-Content-Type-Options": "nosniff",
    # This API is never legitimately framed.
    "X-Frame-Options": "DENY",
    # Do not leak the requested URL to third parties. There is no third party here, which is the
    # point: the header keeps it that way if one is ever introduced.
    "Referrer-Policy": "no-referrer",
    # Nothing this application serves needs a camera, a microphone, or a location.
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
    # `default-src 'none'` suits a JSON API. `/docs` needs its own bundle, so script and style are
    # allowed from self plus the CDN Swagger UI is served from; `unsafe-inline` for style only,
    # which Swagger UI requires and which cannot execute.
    "Content-Security-Policy": (
        "default-src 'none'; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
        "img-src 'self' data: https://fastapi.tiangolo.com; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'none'"
    ),
    # A lab on loopback has no TLS, so HSTS would be actively wrong -- it would pin a browser to
    # https for localhost and break the next application to bind there. Deliberately absent.
    "Cache-Control": "no-store",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach :data:`SECURITY_HEADERS` to every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            # setdefault semantics: a route that deliberately set its own value keeps it.
            response.headers.setdefault(header, value)
        return response


class RateLimitPlaceholderMiddleware(BaseHTTPMiddleware):
    """Counts requests per path. Enforces nothing, and says so.

    The counter is process-local and unbounded in time; it is diagnostic, not a control. It exists so
    that the shape of real traffic is visible before a limiter is designed around a guess.
    """

    #: Declared so ``GET /health`` and the docs can state plainly that this enforces nothing.
    enforcing = False

    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]  # Starlette types this as ASGIApp
        self.counts: Counter[str] = Counter()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        self.counts[request.url.path] += 1
        response = await call_next(request)
        # Stated in the response so a caller inspecting headers is not misled into believing a
        # limiter is protecting this endpoint.
        response.headers.setdefault("X-RateLimit-Policy", "none; not implemented")
        return response
