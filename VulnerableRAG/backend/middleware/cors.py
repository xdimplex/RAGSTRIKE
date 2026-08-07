"""CORS configuration.

Only the two Streamlit origins are allowed, from ``server.cors_origins``. That is not a security
control -- CORS is a browser convention, and RAGStrike will call this API directly with no browser
involved -- it simply keeps the lab's own UI working without opening the API to every page the
operator happens to have open.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rag.config import Settings


def install_cors(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.server.cors_origins or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time-ms"],
    )
