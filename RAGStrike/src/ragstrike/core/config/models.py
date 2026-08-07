"""Configuration schema.

Pydantic, because this is a boundary. Domain entities are frozen dataclasses and must never inherit
from ``BaseModel``; configuration and the HTTP surface are the only two places Pydantic belongs.

Validation happens once, at startup, and fails fast with the exact field path. A scan runs for
minutes -- discovering at minute nine that ``max_qps`` was a string is not acceptable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RetrySettings(BaseModel):
    """Transport-level retry for target requests.

    Declared in the design from Phase 1 and never modelled, so ``engine.retry`` in the shipped
    configuration was silently discarded.

    WHAT IS AND IS NOT RETRIED
        Transport failures, 429, and 5xx. **Never a refusal, and never a 4xx other than 429.** A
        target declining to answer is the single most interesting result an attack pack can get;
        retrying it would turn evidence into noise and inflate the request count against a system
        someone owns.
    """

    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_base_s: float = Field(default=1.0, gt=0)
    backoff_max_s: float = Field(default=30.0, gt=0)
    jitter: bool = True


class EngineSettings(BaseModel):
    """Execution limits.

    Phase 3 runs plugins sequentially, so ``max_concurrency`` is declared and honoured as a value
    but not yet acted on -- the scheduler documents where it will be used. ``max_qps`` is likewise
    carried through now so that no future change has to introduce a rate limit that was never there
    (ADR-017: the limiter has no disable path).
    """

    model_config = ConfigDict(extra="forbid")

    max_concurrency: int = Field(default=4, ge=1, le=64)
    max_qps: float = Field(default=2.0, gt=0)
    probe_timeout_s: int = Field(default=60, gt=0)
    case_timeout_s: int = Field(default=180, gt=0)
    scan_timeout_s: int = Field(default=3600, gt=0)
    retry: RetrySettings = Field(default_factory=RetrySettings)


class PluginSettings(BaseModel):
    """Where plugins come from.

    Two discovery mechanisms, both active (ADR-002): the ``ragstrike.attack_packs`` entry-point
    group for pip-installed packs, and these directories for local and in-development ones.
    """

    model_config = ConfigDict(extra="forbid")

    entry_point_group: str = "ragstrike.attack_packs"
    #: Scanned in order. ``./plugins`` is the drop-in directory; ``./packs`` is the Annex A name and
    #: is kept so a pack placed in either location is found.
    local_dirs: list[Path] = Field(default_factory=lambda: [Path("./plugins"), Path("./packs")])
    disabled: list[str] = Field(default_factory=list)
    #: Packs asking for network egress or filesystem writes are refused unless this is set.
    allow_elevated_permissions: bool = False


class StorageSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    database_path: Path = Path("./data/scans.db")
    reports_dir: Path = Path("./reports")

    def resolve(self, root: Path) -> StorageSettings:
        """Anchor relative paths to the repository root, not the launch directory."""
        return StorageSettings(
            database_path=root / self.database_path,
            reports_dir=root / self.reports_dir,
        )


class SafetySettings(BaseModel):
    """The controls that make this tool safe to ship.

    The shipped defaults mean a fresh install can only reach this machine. Pointing RAGStrike at
    anything else takes two deliberate steps -- flipping ``allow_remote_targets`` *and* adding an
    allowlist entry -- because accidentally scanning a third party is an incident, not an
    inconvenience (ADR-017).
    """

    model_config = ConfigDict(extra="forbid")

    require_authorization: bool = True
    allow_remote_targets: bool = False
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1", "::1"])


class LoggingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str = "INFO"
    log_dir: Path = Path("./logs")
    json_lines: bool = True
    console: bool = True

    @field_validator("level")
    @classmethod
    def _upper(cls, value: str) -> str:
        allowed = {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(f"level must be one of {sorted(allowed)}, got {value!r}")
        return upper


class Settings(BaseModel):
    """The merged, validated configuration."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    engine: EngineSettings = Field(default_factory=EngineSettings)
    plugins: PluginSettings = Field(default_factory=PluginSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    safety: SafetySettings = Field(default_factory=SafetySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    def snapshot(self) -> dict[str, Any]:
        """Serializable copy, stored on the scan record so history stays explicable."""
        return self.model_dump(mode="json")
