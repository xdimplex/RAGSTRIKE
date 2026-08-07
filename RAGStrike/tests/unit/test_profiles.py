"""Scan profile tests.

``configs/profiles/*.yaml`` shipped from Phase 1 and nothing read them until Phase 16. These tests
exist so that cannot happen again quietly: if profile loading is ever disconnected from the planner,
:func:`test_a_profile_narrows_the_plan` fails.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ragstrike.core.config.loader import load_settings
from ragstrike.core.config.profiles import (
    ScanProfile,
    available_profiles,
    load_all_profiles,
    load_profile,
)
from ragstrike.core.errors import ConfigurationError


def _write(root: Path, name: str, body: str) -> None:
    directory = root / "configs" / "profiles"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.yaml").write_text(body, encoding="utf-8")


# ------------------------------------------------------------------------------------------------
# Loading
# ------------------------------------------------------------------------------------------------


def test_a_profile_loads_from_disk(lab_root: Path) -> None:
    _write(
        lab_root,
        "smoke",
        "profile:\n  id: smoke\n  name: Smoke\n  packs: [prompt-injection]\n"
        "  payload_tiers: [quick]\n  attempts: 2\n",
    )

    profile = load_profile("smoke", root=lab_root)

    assert profile.id == "smoke"
    assert profile.packs == ["prompt-injection"]
    assert profile.attempts == 2


def test_a_missing_profile_names_the_ones_that_exist(lab_root: Path) -> None:
    _write(lab_root, "smoke", "profile:\n  id: smoke\n")

    with pytest.raises(ConfigurationError) as caught:
        load_profile("nope", root=lab_root)

    # The hint carries the recovery path; the message carries the fact. The CLI prints both.
    assert "smoke" in caught.value.hint


def test_an_unknown_field_is_rejected_by_name(lab_root: Path) -> None:
    """Misspelling ``payload_tiers`` would silently widen the scan."""
    _write(lab_root, "typo", "profile:\n  id: typo\n  payload_tier: [quick]\n")

    with pytest.raises(ConfigurationError) as caught:
        load_profile("typo", root=lab_root)

    assert "payload_tier" in str(caught.value)


def test_an_unknown_payload_tier_is_rejected(lab_root: Path) -> None:
    _write(lab_root, "bad", "profile:\n  id: bad\n  payload_tiers: [exhaustive]\n")

    with pytest.raises(ConfigurationError) as caught:
        load_profile("bad", root=lab_root)

    assert "exhaustive" in str(caught.value)


@pytest.mark.parametrize("name", ["../../etc/passwd", "../secrets"])
def test_a_profile_name_cannot_escape_the_profile_directory(lab_root: Path, name: str) -> None:
    """The name reaches this function from the CLI and, once the API runs, from an HTTP request."""
    with pytest.raises(ConfigurationError):
        load_profile(name, root=lab_root)


def test_listing_skips_a_broken_profile_rather_than_failing(lab_root: Path) -> None:
    """One malformed file must not make the others unlistable."""
    _write(lab_root, "good", "profile:\n  id: good\n")
    _write(lab_root, "broken", "profile:\n  id: broken\n  attempts: -4\n")

    assert available_profiles(root=lab_root) == ["broken", "good"]
    assert [p.id for p in load_all_profiles(root=lab_root)] == ["good"]


# ------------------------------------------------------------------------------------------------
# Selection
# ------------------------------------------------------------------------------------------------


def test_an_empty_pack_list_selects_everything() -> None:
    """A profile that forgot its packs must run a full scan, not a silent zero-plugin one."""
    profile = ScanProfile(id="empty")

    assert profile.selects("prompt-injection") is True


def test_a_wildcard_selects_everything(lab_root: Path) -> None:
    """``deep.yaml`` writes ``packs: ["*"]``.

    Read literally that is one pack whose slug is ``*``, which matches nothing -- a deep scan that
    runs zero plugins and reports no findings, indistinguishable from a clean result.
    """
    _write(lab_root, "everything", 'profile:\n  id: everything\n  packs: ["*"]\n')

    profile = load_profile("everything", root=lab_root)

    assert profile.packs == []
    assert profile.selects("anything-at-all") is True


def test_a_named_pack_list_excludes_the_rest() -> None:
    profile = ScanProfile(id="narrow", packs=["prompt-injection"])

    assert profile.selects("prompt-injection") is True
    assert profile.selects("prompt-leakage") is False


# ------------------------------------------------------------------------------------------------
# Wiring
# ------------------------------------------------------------------------------------------------


def test_a_profile_overrides_engine_limits(lab_root: Path) -> None:
    _write(lab_root, "brief", "profile:\n  id: brief\n  engine:\n    scan_timeout_s: 120\n")

    profile = load_profile("brief", root=lab_root)
    settings = load_settings(root=lab_root, profile=profile)

    assert settings.engine.scan_timeout_s == 120


def test_a_profile_cannot_widen_the_safety_envelope(lab_root: Path) -> None:
    """Depth is the operator's choice. The safety envelope is not.

    A profile that could set ``allow_remote_targets`` would be a way to reach a third-party host by
    editing a file that reads like a depth preset.
    """
    _write(
        lab_root, "sneaky", "profile:\n  id: sneaky\n  safety:\n    allow_remote_targets: true\n"
    )

    with pytest.raises(ConfigurationError):
        load_profile("sneaky", root=lab_root)


# ------------------------------------------------------------------------------------------------
# The shipped profiles
#
# These assert against the real files in configs/profiles/, not fixtures. Every pack a shipped
# profile names must exist, because a profile naming a pack nobody built produces a scan narrower
# than its own description -- which is exactly what quick.yaml and standard.yaml did until Phase 16.
# ------------------------------------------------------------------------------------------------

#: Every pack this repository actually ships. Update when a pack is added or removed.
INSTALLED_PACKS = frozenset(
    {
        "prompt-injection",
        "prompt-leakage",
        "context-poisoning",
        "prompt-boundary",
        "context-separation",
        "instruction-priority",
        "source-attribution",
        "retrieval-consistency",
        "dummy-attack",
    }
)


def _shipped() -> list[ScanProfile]:
    from ragstrike.core.config.loader import REPO_ROOT

    return load_all_profiles(root=REPO_ROOT)


def test_every_shipped_profile_loads() -> None:
    assert {p.id for p in _shipped()} == {"smoke", "quick", "standard", "deep"}


@pytest.mark.parametrize("profile_id", ["smoke", "quick", "standard", "deep"])
def test_a_shipped_profile_names_only_packs_that_exist(profile_id: str) -> None:
    """The Phase 16 defect, as a regression test.

    ``quick.yaml`` named ``role-override`` and ``secret-extraction``; ``standard.yaml`` named six
    more. None were built. Both scans silently ran a fraction of what their files described.
    """
    profile = next(p for p in _shipped() if p.id == profile_id)

    unbuilt = [slug for slug in profile.requested_packs() if slug not in INSTALLED_PACKS]

    assert unbuilt == [], f"{profile_id}.yaml names packs that do not exist: {unbuilt}"


def test_the_profiles_form_a_ladder() -> None:
    """smoke ⊂ quick ⊂ standard ⊆ deep, in both breadth and attempts.

    A "deeper" profile that tested fewer things than a shallower one would be a trap, and nothing
    else in the system would catch it.
    """
    by_id = {p.id: p for p in _shipped()}

    def breadth(profile: ScanProfile) -> int:
        return len(INSTALLED_PACKS) if not profile.packs else len(profile.packs)

    assert breadth(by_id["smoke"]) < breadth(by_id["quick"]) < breadth(by_id["standard"])
    assert breadth(by_id["standard"]) <= breadth(by_id["deep"])
    assert (
        by_id["smoke"].attempts
        <= by_id["quick"].attempts
        < by_id["standard"].attempts
        < by_id["deep"].attempts
    )


def test_smoke_keeps_the_diagnostic_and_adds_one_real_pack() -> None:
    """Smoke answers two questions now, and it needed to.

    It kept only ``dummy-attack``, whose ``analyze()`` is hardcoded to PASS -- its own comment says
    "this one reports the target resisted, because it never attacked it". So a smoke scan reported
    ZERO findings against a deliberately vulnerable application every time, by construction, and
    that output was repeatedly read as "the target is clean".

    The diagnostic stays first, because a FAIL there still means the HARNESS is broken rather than
    the target -- a genuinely different problem, and worth ruling out before a long scan. One real
    attack pack now follows it, at the quick tier only, so smoke also demonstrates something.
    """
    smoke = next(p for p in _shipped() if p.id == "smoke")

    assert smoke.requested_packs() == ["dummy-attack", "prompt-injection"]
    assert smoke.selects("dummy-attack")
    assert smoke.selects("prompt-injection")
    # Quick tier only -- this is what keeps it to ~90 seconds rather than the full 17 payloads.
    assert smoke.payload_tiers == ["quick"]
    assert smoke.attempts == 1


def test_quick_includes_the_diagnostic() -> None:
    """The old quick profile skipped ``dummy-attack``, so the documented first debugging step was
    excluded from the profile recommended for a first run."""
    quick = next(p for p in _shipped() if p.id == "quick")

    assert quick.selects("dummy-attack")


def test_a_profiles_timeout_can_accommodate_its_own_workload() -> None:
    """``quick.yaml`` allowed 120 seconds for roughly 19 model calls.

    At 5-40 seconds per call on CPU that budget could never be met, and a scan that exceeds it is
    truncated -- producing a partial result that still renders as a completed one.
    """
    by_id = {p.id: p for p in _shipped()}

    assert by_id["smoke"].engine.scan_timeout_s is not None
    assert by_id["quick"].engine.scan_timeout_s >= 600
    assert by_id["standard"].engine.scan_timeout_s >= 3600
    assert by_id["deep"].engine.scan_timeout_s >= 7200
