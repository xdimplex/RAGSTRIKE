"""Loopback-only scope enforcement.

The property under test is not "the guard exists" but "the guard cannot be skipped". Before Phase 6
the check lived at the call sites, and ``ragstrike targets --verify`` did not repeat it -- so a
non-loopback host in ``targets.yaml`` got probed by a command that never asked whether it was
allowed to. These tests pin the guard to ``build_adapter``, the single construction chokepoint, so
that regression cannot recur silently.
"""

from __future__ import annotations

import pytest

from ragstrike.core.errors import TargetError
from ragstrike.models.entities.target import Target
from ragstrike.target_adapters.registry import build_adapter


def target_at(url: str) -> Target:
    return Target(id="t1", name="fixture", adapter="fastapi", url=url)


# -- the shipped default is loopback-only --------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:9000",
        "http://localhost:9000",
        "http://[::1]:9000",
        "http://127.0.0.2:9000",  # the whole 127/8 block is loopback, not just .0.1
    ],
)
def test_loopback_is_allowed_with_no_configuration_at_all(url: str) -> None:
    """Loopback needs no allowlist entry. The shipped default of "no allowlist" is therefore
    exactly the localhost-only policy rather than an approximation of it."""
    assert build_adapter(target_at(url)) is not None


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com:9000",
        "http://10.0.0.5:9000",
        "http://192.168.1.10:9000",
        "http://169.254.169.254/latest/meta-data",  # cloud metadata, the classic SSRF pivot
    ],
)
def test_non_loopback_is_refused_by_default(url: str) -> None:
    with pytest.raises(TargetError):
        build_adapter(target_at(url))


def test_a_caller_that_forgets_the_policy_gets_the_safe_behaviour() -> None:
    """The regression guard for the original bug. ``build_adapter`` with no policy arguments is
    what a future call site will write by accident; it must refuse, not permit."""
    with pytest.raises(TargetError):
        build_adapter(target_at("http://example.com:9000"))


# -- opting out takes two deliberate steps ---------------------------------------------------------


def test_allow_remote_alone_is_not_enough() -> None:
    """Flipping the flag without naming the host still refuses. Two steps, deliberately."""
    with pytest.raises(TargetError):
        build_adapter(target_at("http://example.com:9000"), allow_remote=True, allowed_hosts=[])


def test_allowlist_alone_is_not_enough() -> None:
    with pytest.raises(TargetError):
        build_adapter(
            target_at("http://example.com:9000"),
            allow_remote=False,
            allowed_hosts=["example.com"],
        )


def test_both_together_permit_the_host() -> None:
    adapter = build_adapter(
        target_at("http://example.com:9000"),
        allow_remote=True,
        allowed_hosts=["example.com"],
    )

    assert adapter is not None


def test_an_allowlisted_host_does_not_permit_a_different_one() -> None:
    with pytest.raises(TargetError):
        build_adapter(
            target_at("http://other.example.org:9000"),
            allow_remote=True,
            allowed_hosts=["example.com"],
        )


# -- the refusal explains itself -----------------------------------------------------------------


def test_the_refusal_names_the_host_and_says_how_to_permit_it() -> None:
    with pytest.raises(TargetError) as excinfo:
        build_adapter(target_at("http://example.com:9000"))

    assert "example.com" in excinfo.value.message
    assert "allow_remote_targets" in excinfo.value.hint
