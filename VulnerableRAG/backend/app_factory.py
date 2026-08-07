"""FastAPI application factory.

Builds an app for a given profile. Both VulnerableRAG and SecureRAG will use this same factory --
the difference between them arrives entirely through the engine's policy chain, never through a
branch here.

Two things this module owns:

**The error table.** Every application error maps to an HTTP status in one place, so the mapping is
reviewable. Nothing else in the codebase raises ``HTTPException``.

**The always-JSON guarantee.** Validation errors, application errors, and unhandled exceptions all
come back in the same envelope. The API is a machine interface first; an HTML error page from a
default handler would break every client that assumes otherwise.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.middleware.cors import install_cors
from backend.middleware.logging import RequestLoggingMiddleware
from backend.routers import chat, documents, health, upload
from backend.schemas.errors import ErrorDetail, ErrorResponse
from database.migrations.runner import run_migrations
from rag.config import Settings
from rag.errors import (
    DocumentNotFoundError,
    DocumentTooLargeError,
    EmptyDocumentError,
    EmptyModelResponseError,
    InvalidDocumentError,
    InvalidRequestError,
    ModelNotFoundError,
    ModelTimeoutError,
    ModelUnavailableError,
    NoDocumentsError,
    UnsupportedFileTypeError,
    VectorStoreUnavailableError,
    VulnerableRagError,
)
from rag.generation.llm_client import LLMClient
from rag.policy.protocol import PolicyRejectionError

log = logging.getLogger(__name__)

#: Application error -> HTTP status. The whole mapping, in one table.
STATUS_BY_ERROR: dict[type[Exception], int] = {
    InvalidRequestError: 400,
    InvalidDocumentError: 400,
    EmptyDocumentError: 422,
    UnsupportedFileTypeError: 415,
    DocumentTooLargeError: 413,
    DocumentNotFoundError: 404,
    NoDocumentsError: 409,
    PolicyRejectionError: 400,
    ModelNotFoundError: 503,
    ModelUnavailableError: 503,
    ModelTimeoutError: 504,
    EmptyModelResponseError: 502,
    VectorStoreUnavailableError: 503,
}

DESCRIPTION = """
An **intentionally vulnerable** Retrieval-Augmented Generation application, built as a target for
security testing.

It has no input validation, no output filtering, no context sanitization, and no prompt protection.
It will follow instructions found in uploaded documents and disclose its own system prompt on
request. That is the specification, not a defect -- see `docs/vulnerabilities.md`.

**Never deploy this anywhere reachable.**
"""


def create_app(
    *,
    profile: str = "vulnerable",
    settings: Settings | None = None,
    root: Path | None = None,
    llm_client: LLMClient | None = None,
) -> FastAPI:
    """Build the application.

    Args:
        profile: Which profile to assemble.
        settings: Pre-built settings; loaded from YAML when omitted.
        root: Repository root, for tests running against a temp directory.
        llm_client: Substitute model client, so tests can run the full API without Ollama.
    """
    # Imported here rather than at module scope: SecureRAG will register its own builder, and the
    # factory should not hold a hard import of one profile.
    from profiles.vulnerable.profile import build_engine

    engine = build_engine(settings=settings, root=root, llm_client=llm_client)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        applied = await run_migrations(engine.database)
        if applied:
            log.info("migrations applied", extra={"versions": applied})
        engine.settings.storage.upload_dir.mkdir(parents=True, exist_ok=True)
        engine.settings.storage.log_dir.mkdir(parents=True, exist_ok=True)
        log.warning(
            "%s profile ready on the API -- %d security policies active",
            engine.profile.upper(),
            len(engine.policies),
        )
        yield

    app = FastAPI(
        title=f"VulnerableRAG ({profile})",
        description=DESCRIPTION,
        version=health.VERSION,
        lifespan=lifespan,
    )
    app.state.engine = engine

    install_cors(app, engine.settings)
    app.add_middleware(RequestLoggingMiddleware)

    app.include_router(health.router)
    app.include_router(upload.router)
    app.include_router(documents.router)
    app.include_router(chat.router)

    _install_error_handlers(app)
    return app


def _install_error_handlers(app: FastAPI) -> None:
    """Guarantee that every response is JSON in the same envelope."""

    def envelope(code: str, message: str, hint: str, request: Request) -> dict:
        return ErrorResponse(
            error=ErrorDetail(
                code=code,
                message=message,
                hint=hint,
                request_id=getattr(request.state, "request_id", ""),
            )
        ).model_dump()

    @app.exception_handler(PolicyRejectionError)
    async def _policy_rejected(request: Request, exc: PolicyRejectionError) -> JSONResponse:
        # Never reached by VulnerableRAG -- it has no policies. Wired now so SecureRAG's refusal
        # path is part of the contract from the start rather than bolted on later.
        return JSONResponse(
            status_code=400,
            content=envelope("policy_rejected", exc.reason, f"Blocked by {exc.policy}.", request),
        )

    @app.exception_handler(VulnerableRagError)
    async def _application_error(request: Request, exc: VulnerableRagError) -> JSONResponse:
        status = next(
            (code for kind, code in STATUS_BY_ERROR.items() if isinstance(exc, kind)), 500
        )
        log.warning(
            "application error",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "code": exc.code,
                "status": status,
                "path": request.url.path,
            },
        )
        return JSONResponse(
            status_code=status, content=envelope(exc.code, exc.message, exc.hint, request)
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err.get('loc', []))}: {err.get('msg', '')}"
            for err in exc.errors()
        )
        return JSONResponse(
            status_code=422,
            content=envelope(
                "invalid_request",
                f"Request validation failed: {problems}",
                "Check the field names and types against /docs.",
                request,
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception(
            "unhandled error",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
            },
        )
        return JSONResponse(
            status_code=500,
            content=envelope(
                "internal_error",
                f"{type(exc).__name__}: {exc}",
                "Check logs/ for the full traceback, matched by request id.",
                request,
            ),
        )
