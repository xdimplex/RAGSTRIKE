"""The UI must introduce itself as the lab it actually is.

WHY THIS FILE EXISTS
    SecureRAG is a fork of VulnerableRAG that shares its whole ``frontend/`` package. Every page in
    that package used to hardcode the string "VulnerableRAG" in ``st.set_page_config``, in the page
    title, and in the home page prose -- so the hardened lab presented itself as the vulnerable one,
    all the way down to telling the operator to start it with ``profiles.vulnerable.main_api``.

    Nothing caught it. The parity suite asserts the two labs behave IDENTICALLY on benign input,
    which is exactly why it could never notice: identical is what it was checking for. Branding is
    the one thing that must differ, so it needs its own test.

    This matters beyond cosmetics. The entire value of the differential comparison rests on a reader
    knowing which lab produced which result. A hardened target labelled "VulnerableRAG" in a
    screenshot is worse than no label at all.

WHAT IT LOCKS DOWN
    That the display name is DERIVED from ``settings.profile`` rather than typed in, and that no page
    reintroduces a literal.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import frontend._bootstrap as bootstrap

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"

#: The profile this repository ships, and the name its UI must show.
EXPECTED_PROFILE = "vulnerable"
EXPECTED_NAME = "VulnerableRAG"


def test_this_repo_defaults_to_its_own_profile() -> None:
    """A UI started without VRAG_PROFILE must not load the other lab's configuration."""
    assert bootstrap.DEFAULT_PROFILE == EXPECTED_PROFILE


def test_the_display_name_follows_the_profile() -> None:
    settings = bootstrap.get_settings(EXPECTED_PROFILE)

    assert settings.profile == EXPECTED_PROFILE
    assert bootstrap.app_name(settings) == EXPECTED_NAME


def test_the_other_profile_still_resolves_to_its_own_name() -> None:
    """One codebase, two labs (ADR-009): the mapping has to work in both directions."""
    assert bootstrap.app_name(bootstrap.get_settings("secure")) == "SecureRAG"


def test_page_titles_are_scoped_to_the_app_name() -> None:
    settings = bootstrap.get_settings(EXPECTED_PROFILE)

    assert bootstrap.page_title(settings, "Chat") == f"Chat · {EXPECTED_NAME}"
    assert bootstrap.page_title(settings) == EXPECTED_NAME


@pytest.mark.parametrize(
    "page",
    sorted(p for p in FRONTEND.rglob("*.py") if "__pycache__" not in str(p)),
    ids=lambda p: str(p.relative_to(FRONTEND)) if isinstance(p, Path) else str(p),
)
def test_no_page_hardcodes_a_lab_name_in_set_page_config(page: Path) -> None:
    """``set_page_config`` must take a derived title, never a literal.

    Checking the call rather than the whole file keeps the branding map in ``_bootstrap`` and the
    explanatory prose in docstrings legal, while still failing the moment someone types a lab name
    back into a page header.
    """
    source = page.read_text(encoding="utf-8")

    for call in re.findall(r"st\.set_page_config\((.*?)\)", source, flags=re.DOTALL):
        assert "VulnerableRAG" not in call, f"{page.name} hardcodes a lab name in set_page_config"
        assert "SecureRAG" not in call, f"{page.name} hardcodes a lab name in set_page_config"
