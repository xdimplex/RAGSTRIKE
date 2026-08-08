"""Import bootstrap for the Streamlit pages.

Streamlit puts the *script's* directory on ``sys.path``, not the working directory, so a page inside
``frontend/pages/`` cannot ``import rag.config`` without help. Every page imports this module first.

It also loads settings once and exposes the API base URL, so no page has to work out where the
backend lives.
"""

# ruff: noqa: I001 - the import order here is deliberate: everything below the sys.path
# fix must stay below it, and sorting the block would move it above.

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import os  # noqa: E402  - must follow the sys.path fix

from rag.config import Settings, load_settings  # noqa: E402


#: The profile this repository ships. `load_settings` already defaults to it; the fallback below has
#: to agree, or a UI started without VRAG_PROFILE quietly loads the WRONG lab's configuration --
#: which is how this repo's UI ended up titled "VulnerableRAG".
DEFAULT_PROFILE = "secure"

#: Display name and icon per profile. The frontend is deliberately one codebase serving both labs
#: (ADR-009), so the name has to be DERIVED rather than typed into each page. Every page used to
#: hardcode "VulnerableRAG" -- a fork leftover that made the hardened lab introduce itself as the
#: vulnerable one, which is the single most misleading thing this UI could have said.
_BRANDING = {
    "vulnerable": ("VulnerableRAG", "⚠️"),
    "secure": ("SecureRAG", "🛡️"),
}


@lru_cache(maxsize=4)
def get_settings(profile: str | None = None) -> Settings:
    """Load settings for the active profile.

    ``VRAG_PROFILE`` selects it, so one UI codebase serves both profiles -- which is the whole point
    of a shared frontend (ADR-009).
    """
    return load_settings(profile or os.environ.get("VRAG_PROFILE", DEFAULT_PROFILE))


def app_name(settings: Settings) -> str:
    """The lab's display name, from its profile. Never hardcode this in a page."""
    return _BRANDING.get(settings.profile, (settings.profile.title() + "RAG", "🔹"))[0]


def app_icon(settings: Settings) -> str:
    """The lab's page icon, from its profile."""
    return _BRANDING.get(settings.profile, ("", "🔹"))[1]


def page_title(settings: Settings, section: str = "") -> str:
    """Browser tab title: ``"Chat · SecureRAG"``, or just the app name on the home page."""
    name = app_name(settings)
    return f"{section} · {name}" if section else name


def api_base_url(settings: Settings) -> str:
    """Where the backend lives.

    ``VRAG_API_URL`` wins, so the UI can point at a container or a different port without editing
    configuration.
    """
    override = os.environ.get("VRAG_API_URL")
    if override:
        return override.rstrip("/")
    return f"http://{settings.server.host}:{settings.server.api_port}"
