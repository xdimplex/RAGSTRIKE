"""The application factory.

WHY A FACTORY RATHER THAN A MODULE-LEVEL ``app``
    A module-level ``app = FastAPI()`` builds a database connection and discovers plugins at import
    time. That makes the module unimportable without a working environment, makes tests share one
    instance, and makes ``uvicorn --reload`` do real work on every file save. A factory takes
    settings and returns an app.

WHY IT BINDS TO LOOPBACK
    The same policy the scanner applies to its targets applies to itself. This API can start a scan;
    exposing it on ``0.0.0.0`` would let anyone on the network do so. :func:`run` binds ``127.0.0.1``
    and there is no flag here to change it -- someone who genuinely needs that can put a reverse
    proxy in front and own the decision explicitly.

WHY THERE IS NO AUTHENTICATION
    Stated plainly rather than left to be discovered: there is none. The control is that nothing
    outside this machine can reach the socket. If that ever stops being true, authentication has to
    arrive in the same change -- see ``docs/limitations.md``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ragstrike import __version__
from ragstrike.api.errors import install_error_handlers
from ragstrike.api.middleware.correlation import CorrelationMiddleware
from ragstrike.api.routers import packs, reports, scans, system, targets
from ragstrike.api.service import ScanService
from ragstrike.api.streaming import progress
from ragstrike.core.config.loader import load_settings
from ragstrike.core.config.models import Settings
from ragstrike.logging.setup import setup_logging

log = logging.getLogger(__name__)

API_PREFIX = "/api/v1"

#: The dashboard runs on its own Streamlit port, so it is a cross-origin caller. Loopback only --
#: a wildcard here would let any page the operator happens to visit drive this API.
_ALLOWED_ORIGINS = [
    "http://localhost:8501",
    "http://127.0.0.1:8501",
]

DESCRIPTION = """
The HTTP surface of the RAGStrike engine.

**Local only.** This API can start attack scans. It binds to loopback, has no authentication, and
relies on the socket being unreachable from outside this machine.

Every error uses one envelope: `{"error": {"code", "message", "details", "correlation_id"}}`.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application.

    Args:
        settings: Engine configuration. Loaded from ``configs/ragstrike.yaml`` when omitted; passed
            explicitly by tests so each gets its own database and plugin directory.
    """
    resolved = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        service = ScanService(resolved)
        await service.startup()
        app.state.service = service
        try:
            yield
        finally:
            # Cancels anything still running. A scan holds an open connection to a live target;
            # exiting without cancelling leaves its row stuck in RUNNING, which later reads as a
            # scan that never ended.
            await service.shutdown()

    app = FastAPI(
        title="RAGStrike API",
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )

    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Correlation-ID"],
    )

    install_error_handlers(app)

    for router in (system.router, targets.router, packs.router, scans.router, progress.router):
        app.include_router(router, prefix=API_PREFIX)
    app.include_router(reports.router, prefix=API_PREFIX)

    log.debug("api application built", extra={"routes": len(app.routes)})
    return app


def run(host: str = "127.0.0.1", port: int = 8000) -> None:  # pragma: no cover - entry point
    """Serve the API.

    ``host`` defaults to loopback and callers should leave it there. It is a parameter rather than a
    constant only so a test can bind an ephemeral interface; the CLI does not expose it.
    """
    import uvicorn  # noqa: PLC0415 - optional server dep, deferred so create_app stays usable

    settings = load_settings()
    setup_logging(
        log_dir=settings.logging.log_dir,
        level=settings.logging.level,
        json_lines=settings.logging.json_lines,
        console=settings.logging.console,
    )
    uvicorn.run(create_app(settings), host=host, port=port, log_config=None)


__all__ = ["API_PREFIX", "create_app", "run"]
