"""Dependency wiring.

The engine is built once at startup and stashed on ``app.state``. Handlers ask for it through
``get_engine``, which means tests can build an app with a scripted model client and exercise every
endpoint without Ollama running.
"""

from __future__ import annotations

from fastapi import Request

from rag.engine import Engine


def get_engine(request: Request) -> Engine:
    """Return the engine assembled at startup."""
    return request.app.state.engine


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")
