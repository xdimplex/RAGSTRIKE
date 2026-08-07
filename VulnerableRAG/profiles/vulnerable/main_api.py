"""API entry point for VulnerableRAG.

    RAGSTRIKE_LAB_ACK=1 python -m profiles.vulnerable.main_api

or, for auto-reload during development:

    RAGSTRIKE_LAB_ACK=1 uvicorn profiles.vulnerable.main_api:app --port 9000 --reload

The ``app`` object is importable either way, but note that the acknowledgement gate only runs on the
``python -m`` path -- uvicorn imports the module and never calls ``main()``. That is a deliberate
trade: reload-driven development would be unusable if every reload aborted, and the operator has
already acknowledged once to get the server up.
"""

from __future__ import annotations

import logging

import uvicorn

from backend.app_factory import create_app
from profiles.vulnerable.profile import PROFILE_NAME, require_lab_acknowledgement
from rag.config import load_settings
from rag.logging_setup import setup_logging

settings = load_settings(PROFILE_NAME)
setup_logging(settings.storage.log_dir)

log = logging.getLogger(__name__)

#: The ASGI application. Importable by uvicorn.
app = create_app(profile=PROFILE_NAME, settings=settings)


def main() -> None:
    require_lab_acknowledgement()

    log.warning(
        "Starting VulnerableRAG API on http://%s:%s -- INTENTIONALLY VULNERABLE, loopback only",
        settings.server.host,
        settings.server.api_port,
    )
    uvicorn.run(
        app,
        host=settings.server.host,
        port=settings.server.api_port,
        log_config=None,  # logging is already configured above
    )


if __name__ == "__main__":
    main()
