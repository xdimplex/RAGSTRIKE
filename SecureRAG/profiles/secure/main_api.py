"""API entry point for SecureRAG.

    RAGSTRIKE_LAB_ACK=1 python -m profiles.secure.main_api

or, for auto-reload during development:

    RAGSTRIKE_LAB_ACK=1 uvicorn profiles.secure.main_api:app --port 9001 --reload

Structurally identical to VulnerableRAG's entry point, down to the acknowledgement gate only running
on the ``python -m`` path. Keeping the launch behaviour the same is not cosmetic: an operator
comparing the two applications should not have to learn two ways to start them, and a difference in
startup is a difference that could explain away a difference in scan results.
"""

from __future__ import annotations

import logging

import uvicorn

from backend.app_factory import create_app
from profiles.secure.profile import PROFILE_NAME, require_lab_acknowledgement
from rag.config import load_settings
from rag.logging_setup import setup_logging

settings = load_settings(PROFILE_NAME)
setup_logging(settings.storage.log_dir)

log = logging.getLogger(__name__)

#: The ASGI application. Importable by uvicorn.
app = create_app(profile=PROFILE_NAME, settings=settings)


def main() -> None:
    require_lab_acknowledgement()

    log.info(
        "Starting SecureRAG API on http://%s:%s -- hardened, loopback only",
        settings.server.host,
        settings.server.api_port,
    )
    uvicorn.run(
        app,
        host=settings.server.host,
        port=settings.server.api_port,
        log_config=None,  # logging is already configured above
        server_header=not settings.security.http.suppress_server_header,
    )


if __name__ == "__main__":
    main()
