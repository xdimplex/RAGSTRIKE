"""Streamlit launcher for VulnerableRAG.

    RAGSTRIKE_LAB_ACK=1 python -m profiles.vulnerable.main_ui

Streamlit discovers sibling pages relative to the script it is given, so this launches
``frontend/app.py`` rather than being the Streamlit script itself. That keeps one UI codebase serving
both profiles -- ``VRAG_PROFILE`` selects which one, and the pages read it through
``frontend/_bootstrap.py``.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from profiles.vulnerable.profile import PROFILE_NAME, require_lab_acknowledgement
from rag.config import load_settings
from rag.logging_setup import setup_logging

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> None:
    require_lab_acknowledgement()

    settings = load_settings(PROFILE_NAME)
    setup_logging(settings.storage.log_dir)
    log = logging.getLogger(__name__)

    environment = dict(os.environ)
    environment["VRAG_PROFILE"] = PROFILE_NAME
    environment.setdefault(
        "VRAG_API_URL", f"http://{settings.server.host}:{settings.server.api_port}"
    )
    # Streamlit imports pages from the script's directory; the repo root has to be importable too.
    environment["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + environment.get("PYTHONPATH", "")

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(REPO_ROOT / "frontend" / "app.py"),
        "--server.port",
        str(settings.server.ui_port),
        "--server.address",
        settings.server.host,  # loopback only
        "--browser.gatherUsageStats",
        "false",
        # Without this, a Streamlit that has never run on this machine prints its welcome banner and
        # BLOCKS on stdin waiting for an email address. Launched detached -- which is how anyone runs
        # four services at once -- there is no stdin to answer it, so the UI simply never binds its
        # port and the only symptom is a connection refused. Headless skips the prompt entirely.
        "--server.headless",
        "true",
    ]

    log.warning(
        "Starting VulnerableRAG UI on http://%s:%s -- INTENTIONALLY VULNERABLE, loopback only",
        settings.server.host,
        settings.server.ui_port,
    )
    raise SystemExit(subprocess.call(command, cwd=REPO_ROOT, env=environment))


if __name__ == "__main__":
    main()
