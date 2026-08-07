"""The error envelope, and the mapping from domain errors onto HTTP.

ONE SHAPE, ALWAYS
    Every failure this API produces looks like::

        {"error": {"code": "...", "message": "...", "details": {...},
                   "correlation_id": "..."}}

    including validation failures, which FastAPI would otherwise render in its own ``{"detail": ...}``
    shape. A client that has to parse two error formats will handle one of them badly, and the
    dashboard's :func:`~ragstrike.dashboard.services.errors.from_envelope` already codes against this
    one.

WHY THE CODE IS THE DOMAIN CODE
    ``RAGStrikeError`` subclasses each carry a stable ``code`` (``authorization_error``,
    ``target_unreachable``, ...). Reusing it means the CLI, the API, and the dashboard all name a
    failure identically, so a support conversation about "authorization_error" is about one thing.

WHY HINTS SURVIVE
    Every domain error carries a ``hint`` -- what the operator should actually do. Dropping it at the
    HTTP boundary would leave the API strictly less helpful than the CLI for the same failure.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ragstrike.core.errors import (
    AuthorizationError,
    ConfigurationError,
    PluginError,
    RAGStrikeError,
    TargetNotFoundError,
    TargetTimeoutError,
    TargetUnreachableError,
    UnknownAdapterError,
)

#: Domain error -> HTTP status. Anything unlisted is a 500, which is the correct default: an error
#: nobody mapped is one nobody anticipated.
_STATUS: dict[type[RAGStrikeError], int] = {
    AuthorizationError: status.HTTP_403_FORBIDDEN,
    ConfigurationError: status.HTTP_400_BAD_REQUEST,
    TargetNotFoundError: status.HTTP_404_NOT_FOUND,
    UnknownAdapterError: status.HTTP_400_BAD_REQUEST,
    TargetUnreachableError: status.HTTP_502_BAD_GATEWAY,
    TargetTimeoutError: status.HTTP_504_GATEWAY_TIMEOUT,
    PluginError: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def envelope(
    *,
    code: str,
    message: str,
    details: Any = None,
    correlation_id: str = "",
) -> dict[str, Any]:
    """Build the one error shape this API emits."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "correlation_id": correlation_id,
        }
    }


def status_for(exc: RAGStrikeError) -> int:
    """The HTTP status for a domain error, resolved **most-specific-first**.

    Walks the exception's own MRO rather than iterating the table, because several of these classes
    inherit from each other: ``TargetNotFoundError`` is a ``ConfigurationError``, and
    ``UnknownAdapterError`` is too.

    An ``isinstance`` loop over the table would return whichever entry happened to be declared
    first -- which made ``GET /targets/does-not-exist`` answer **400** instead of 404, because
    ``ConfigurationError`` sat above ``TargetNotFoundError`` in the dict. The MRO is the only order
    that means anything here; dict order is an accident of editing.

    A new subclass with no entry of its own still inherits its parent's status rather than becoming
    a 500.
    """
    for error_type in type(exc).__mro__:
        if error_type in _STATUS:
            return _STATUS[error_type]
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def install_error_handlers(app: FastAPI) -> None:
    """Register the handlers that keep the envelope universal."""

    @app.exception_handler(RAGStrikeError)
    async def _domain_error(request: Request, exc: RAGStrikeError) -> JSONResponse:
        return JSONResponse(
            status_code=status_for(exc),
            content=envelope(
                code=exc.code,
                message=exc.message,
                details={"hint": exc.hint} if exc.hint else {},
                correlation_id=_correlation_id(request),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=envelope(
                code="validation_error",
                message="The request body or query string is not valid.",
                # `errors()` carries ctx objects that are not always JSON-serialisable; the three
                # fields below are the ones a client can act on.
                details={
                    "fields": [
                        {
                            "location": ".".join(str(p) for p in error.get("loc", ())),
                            "message": error.get("msg", ""),
                            "type": error.get("type", ""),
                        }
                        for error in exc.errors()
                    ]
                },
                correlation_id=_correlation_id(request),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(
                code=_CODES.get(exc.status_code, "http_error"),
                message=str(exc.detail),
                correlation_id=_correlation_id(request),
            ),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
        # The message is deliberately generic. An unhandled exception's text can carry a file path,
        # a query fragment, or part of a document -- and this API answers a browser.
        # The correlation id is how the operator finds the real traceback in the log.
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=envelope(
                code="internal_error",
                message="An unexpected error occurred. See the server log.",
                correlation_id=_correlation_id(request),
            ),
        )


#: Statuses worth a stable code, because the dashboard switches on them.
_CODES = {
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_501_NOT_IMPLEMENTED: "not_implemented",
}


def _correlation_id(request: Request) -> str:
    return str(getattr(request.state, "correlation_id", ""))


__all__ = ["envelope", "install_error_handlers", "status_for"]
