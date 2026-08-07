"""Scan profiles -- precedence level 3.

WHY THIS FILE EXISTS
    ``configs/profiles/{quick,standard,deep}.yaml`` shipped from Phase 1 and **nothing ever read
    them**. The dashboard's Scan Center offered a profile picker backed by three hardcoded
    fallbacks; the CLI had no ``--profile`` flag at all; and the SDK constants module referenced
    "future profile-based scan selection". A user who edited ``deep.yaml`` to add a pack saw no
    effect and no error, which is the worst failure mode configuration has.

    This module makes them real.

WHAT A PROFILE SELECTS
    Three things, and deliberately no more:

    * **packs** -- which plugin slugs are in scope. A profile naming a pack that is not installed is
      not an error: profiles are written against the catalog, and an uninstalled pack is a *coverage*
      fact, recorded as a skip with a reason rather than a crash (ADR-020).
    * **payload_tiers** -- how deep to go within each pack.
    * **attempts** -- how many times each payload is tried. LLM behaviour is stochastic, so
      exploitability is a ratio; a higher count buys a more reliable measurement, not redundancy.

    A profile may also override ``engine`` limits, because "deep" and "quick" want different
    timeouts by definition.

WHY AN UNKNOWN PACK IS A SKIP AND AN UNKNOWN FIELD IS AN ERROR
    They are different mistakes. Naming a pack you have not installed is a normal, recoverable state
    that the coverage report exists to describe. Misspelling ``payload_tiers`` as ``payload_tier``
    is a typo that would silently widen the scan -- so ``extra="forbid"`` refuses it by name.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
import yaml

from ragstrike.core.errors import ConfigurationError

#: Where profiles live, relative to the repository root.
PROFILE_DIR = Path("configs") / "profiles"

#: Tiers a payload set may declare. Mirrors ``sdk.constants.PAYLOAD_TIERS``; kept as a literal here
#: because ``core`` must not import the SDK (the dependency rule points inward).
_TIERS = ("quick", "standard", "deep")


class ProfileEngineOverrides(BaseModel):
    """Engine limits a profile may raise or lower."""

    model_config = ConfigDict(extra="forbid")

    max_concurrency: int | None = Field(default=None, ge=1, le=64)
    scan_timeout_s: int | None = Field(default=None, gt=0)


class ScanProfile(BaseModel):
    """A named scan depth."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str = ""
    description: str = ""
    packs: list[str] = Field(default_factory=list)
    payload_tiers: list[str] = Field(default_factory=lambda: list(_TIERS))
    attempts: int = Field(default=1, ge=1, le=100)
    engine: ProfileEngineOverrides = Field(default_factory=ProfileEngineOverrides)
    #: Deterministic ordering. The same seed produces the same plan, which is what makes two runs
    #: comparable at all.
    seed: int = 1337
    #: Cost-amplification cases measure a resource limit by approaching it. They stay out of every
    #: scan unless a profile says otherwise, in its own file, by name -- an operator who has not
    #: thought about it cannot enable it by accident, and one who has leaves a record that they did.
    #: The intent is to measure a ceiling, never to exhaust it.
    acknowledge_cost_amplification: bool = False

    @field_validator("packs")
    @classmethod
    def _expand_wildcard(cls, value: list[str]) -> list[str]:
        """``["*"]`` means every installed pack, and is stored as the empty list.

        ``deep.yaml`` writes ``packs: ["*"]``. Without this it would be read as a single pack whose
        slug is literally ``*``, match nothing, and produce a deep scan that ran zero plugins and
        reported no findings -- which reads identically to a clean result.
        """
        return [] if "*" in value else value

    @field_validator("payload_tiers")
    @classmethod
    def _known_tiers(cls, value: list[str]) -> list[str]:
        unknown = [tier for tier in value if tier not in _TIERS]
        if unknown:
            raise ValueError(f"unknown payload tier(s) {unknown}; valid tiers are {list(_TIERS)}")
        return value

    def requested_packs(self) -> list[str]:
        """Every slug this profile asked for. Empty means "everything installed".

        The planner uses this to notice a profile asking for a pack nobody built -- see
        :class:`~ragstrike.scheduler.scan_scheduler.ProfileSelector`.
        """
        return list(self.packs)

    def selects(self, slug: str) -> bool:
        """Whether *slug* is in scope.

        An empty ``packs`` list means **everything**, not nothing. A profile that forgot to list its
        packs should run a full scan and be obviously wrong, rather than run zero plugins and report
        a clean result -- the failure mode ADR-020 exists to prevent.
        """
        return not self.packs or slug in self.packs


def load_profile(name: str, *, root: Path | None = None) -> ScanProfile:
    """Read ``configs/profiles/<name>.yaml``.

    Raises:
        ConfigurationError: No such profile, malformed YAML, or an invalid field.
    """
    root = root or Path.cwd()
    path = (root / PROFILE_DIR / f"{name}.yaml").resolve()
    directory = (root / PROFILE_DIR).resolve()

    # A profile name arrives from the CLI and, once the API is running, from an HTTP request.
    # `../../etc/passwd` must not resolve outside the profile directory.
    if not path.is_relative_to(directory):
        raise ConfigurationError(
            f"Invalid profile name {name!r}.",
            hint="A profile name is a bare file name, not a path.",
        )

    if not path.exists():
        raise ConfigurationError(
            f"No scan profile named {name!r}.",
            hint=f"Available profiles: {', '.join(available_profiles(root=root)) or 'none'}.",
        )

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"{path} is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigurationError(f"{path} must contain a mapping at the top level.")

    block: Any = raw.get("profile", raw)
    if not isinstance(block, dict):
        raise ConfigurationError(f"{path}: 'profile' must be a mapping.")
    block = {**block}
    block.setdefault("id", name)

    try:
        return ScanProfile.model_validate(block)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise ConfigurationError(
            f"Invalid scan profile in {path}: {problems}",
            hint="Correct the named fields and retry.",
        ) from exc


def available_profiles(*, root: Path | None = None) -> list[str]:
    """Profile names on disk, sorted. Empty when the directory is absent."""
    root = root or Path.cwd()
    directory = root / PROFILE_DIR
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.yaml"))


def load_all_profiles(*, root: Path | None = None) -> list[ScanProfile]:
    """Every valid profile on disk.

    A malformed profile is **skipped rather than fatal** here, because this feeds a listing: one
    broken file must not make the other profiles unlistable. :func:`load_profile` is the strict path,
    and it is the one a scan goes through.
    """
    profiles: list[ScanProfile] = []
    for name in available_profiles(root=root):
        try:
            profiles.append(load_profile(name, root=root))
        except ConfigurationError:
            continue
    return profiles


__all__ = [
    "PROFILE_DIR",
    "ProfileEngineOverrides",
    "ScanProfile",
    "available_profiles",
    "load_all_profiles",
    "load_profile",
]
