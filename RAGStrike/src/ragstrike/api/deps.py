"""Shared dependencies.

The :class:`~ragstrike.api.service.ScanService` is built once during startup and stored on
``app.state``. Reading it from the request rather than from a module-level global is what lets a test
construct an app with its own temporary database and plugin directory -- a global would make every
test in the file share one, and the first one to run would decide what the rest saw.
"""

from __future__ import annotations

from fastapi import Request

from ragstrike.api.service import ScanService


def get_service(request: Request) -> ScanService:
    """The application's :class:`ScanService`, from app state."""
    service = getattr(request.app.state, "service", None)
    if service is None:  # pragma: no cover - only reachable if the lifespan did not run
        raise RuntimeError(
            "ScanService is not initialised. The app must be created by create_app()."
        )
    # `app.state` is an untyped namespace in Starlette, so the cast is where the contract is
    # asserted. The isinstance check makes it an assertion rather than a promise.
    if not isinstance(service, ScanService):  # pragma: no cover - defensive
        raise TypeError(f"app.state.service is {type(service).__name__}, not ScanService.")
    return service


__all__ = ["get_service"]
