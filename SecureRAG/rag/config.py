"""Configuration loading and validation.

Layered YAML load with a documented precedence order:

    configs/config.yaml  ->  profiles/<profile>/config.yaml  ->  VRAG_* environment variables

Validation happens once, at startup, and fails fast. Discovering that ``top_k`` was a string halfway
through a scan is not acceptable.

Note what is deliberately *absent*: there is no toggle anywhere in this schema that adds or removes
a security control. The control chain is composed in code by
``rag.policy.controls.build_controls`` (ADR-009). ``configs/security.yaml`` -- validated separately
in :mod:`rag.security_config` -- tunes thresholds *within* controls, and cannot make one vanish.
A flag that could disable a defence would eventually be flipped by accident, and the application
would report a posture it no longer had.

DIVERGENCE FROM VulnerableRAG
    This file is inherited from VulnerableRAG almost verbatim. The differences are:
    the default profile, the ``SRAG_`` environment prefix (``VRAG_`` still honoured), the added
    ``security`` field, and the loopback warning text. ``docs/compatibility-guide.md`` lists every
    divergence between the two repositories; keeping this one small is what makes them reviewable
    side by side.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from rag.security_config import SecuritySettings, load_security_settings

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_CONFIG = REPO_ROOT / "configs" / "config.yaml"

#: Primary prefix. ``VRAG_`` is still honoured so a lab script written for either application works
#: against both -- one less incidental difference between the two, which is the whole point of the
#: pair. ``SRAG_`` wins where both are set.
ENV_PREFIX = "SRAG_"
LEGACY_ENV_PREFIX = "VRAG_"


class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    api_port: int = 9000
    ui_port: int = 8601
    cors_origins: list[str] = Field(default_factory=list)

    @field_validator("host")
    @classmethod
    def _warn_on_public_bind(cls, value: str) -> str:
        # Not an error -- an operator may have a reason -- but it must never happen silently.
        # docs/LAB_SAFETY.md explains why this application must stay on loopback.
        if value not in {"127.0.0.1", "localhost", "::1"}:
            import warnings

            warnings.warn(
                f"SecureRAG is binding to {value!r}, not loopback. It is hardened, not audited, "
                f"and it is one half of a security lab -- not a production application. "
                f"See docs/LAB_SAFETY.md.",
                stacklevel=2,
            )
        return value


class ModelSettings(BaseModel):
    provider: Literal["ollama"] = "ollama"
    base_url: str = "http://localhost:11434"
    name: str = "qwen3:4b"
    temperature: float = 0.0
    max_tokens: int = 1024
    timeout_s: int = 180
    strip_thinking: bool = True
    #: Ask a thinking model (Qwen3) to reason before answering. Off by default: with it on, the
    #: model can spend the whole ``max_tokens`` budget reasoning and return an empty answer.
    think: bool = False


class EmbeddingSettings(BaseModel):
    provider: Literal["ollama"] = "ollama"
    model: str = "nomic-embed-text"
    timeout_s: int = 60


class IngestionSettings(BaseModel):
    chunk_size: int = Field(default=512, gt=0)
    chunk_overlap: int = Field(default=64, ge=0)
    supported_types: list[str] = Field(
        default_factory=lambda: ["pdf", "txt", "md", "csv"]
    )
    max_upload_mb: int = Field(default=25, gt=0)

    @field_validator("chunk_overlap")
    @classmethod
    def _overlap_below_size(cls, value: int, info: Any) -> int:
        size = info.data.get("chunk_size")
        if size is not None and value >= size:
            raise ValueError(f"chunk_overlap ({value}) must be smaller than chunk_size ({size})")
        return value


class RetrievalSettings(BaseModel):
    top_k: int = Field(default=5, gt=0)
    similarity_threshold: float | None = None


class StorageSettings(BaseModel):
    upload_dir: Path = Path("./uploads")
    chroma_dir: Path = Path("./vectorstore/chroma")
    corpus_dir: Path = Path("./corpus")
    database_path: Path = Path("./data/vulnerable.db")
    log_dir: Path = Path("./logs")

    def resolve(self, root: Path) -> StorageSettings:
        """Return a copy with every relative path anchored to *root*.

        Paths in YAML are relative to the repository, not to whatever directory uvicorn or
        streamlit happened to be launched from.
        """
        return StorageSettings(
            upload_dir=root / self.upload_dir,
            chroma_dir=root / self.chroma_dir,
            corpus_dir=root / self.corpus_dir,
            database_path=root / self.database_path,
            log_dir=root / self.log_dir,
        )


class SessionSettings(BaseModel):
    max_history_turns: int | None = None


class ApiSettings(BaseModel):
    expose_retrieved_chunks: bool = True
    expose_sources: bool = True
    expose_system_prompt: bool = True


class Settings(BaseModel):
    """The fully merged, validated configuration."""

    version: int = 1
    profile: str = "secure"
    system_prompt_path: Path | None = None

    server: ServerSettings = Field(default_factory=ServerSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    session: SessionSettings = Field(default_factory=SessionSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)

    #: Validated ``configs/security.yaml``. Present on SecureRAG only; VulnerableRAG has no such
    #: file and no such field. Every default is the secure value, so a missing file yields a fully
    #: hardened application rather than a disabled one.
    security: SecuritySettings = Field(default_factory=SecuritySettings)

    @property
    def collection_name(self) -> str:
        """One Chroma collection per profile, so the two labs never share vectors."""
        return f"vrag_{self.profile}"

    def system_prompt(self) -> str:
        if self.system_prompt_path is None or not self.system_prompt_path.exists():
            raise FileNotFoundError(
                f"System prompt not found at {self.system_prompt_path}. "
                f"Each profile owns its prompt under profiles/<profile>/prompts/."
            )
        return self.system_prompt_path.read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------------
# Loading
# ------------------------------------------------------------------------------------------------


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursive dict merge. Scalars and lists are replaced wholesale; dicts merge key by key."""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _coerce(raw: str) -> Any:
    """Interpret an environment-variable string as YAML, so ``VRAG_RETRIEVAL__TOP_K=8`` is an int."""
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError:
        return raw


def _env_overrides() -> dict[str, Any]:
    """Collect ``VRAG_SECTION__KEY=value`` variables into a nested dict.

    Double underscore separates nesting levels: ``VRAG_MODEL__NAME`` -> ``{"model": {"name": ...}}``.
    """
    overrides: dict[str, Any] = {}
    # Legacy first, so an SRAG_ value overrides the VRAG_ spelling of the same setting.
    for prefix in (LEGACY_ENV_PREFIX, ENV_PREFIX):
        for env_key, raw in os.environ.items():
            if not env_key.startswith(prefix):
                continue
            path = env_key[len(prefix) :].lower().split("__")
            cursor = overrides
            for part in path[:-1]:
                nested = cursor.setdefault(part, {})
                if not isinstance(nested, dict):
                    nested = {}
                    cursor[part] = nested
                cursor = nested
            cursor[path[-1]] = _coerce(raw)
    return overrides


def load_settings(
    profile: str = "secure",
    *,
    root: Path | None = None,
    extra: dict[str, Any] | None = None,
) -> Settings:
    """Load, merge, and validate configuration for *profile*.

    Args:
        profile: Profile name; selects ``profiles/<profile>/config.yaml``.
        root: Repository root. Defaults to the real one; tests point it at a temp directory.
        extra: Highest-precedence overrides, used by tests.

    Raises:
        pydantic.ValidationError: On any invalid value, with the exact field path.
    """
    root = root or REPO_ROOT
    shared = _read_yaml(root / "configs" / "config.yaml")
    profile_file = _read_yaml(root / "profiles" / profile / "config.yaml")

    merged = _deep_merge(shared, profile_file)
    merged = _deep_merge(merged, _env_overrides())
    if extra:
        merged = _deep_merge(merged, extra)

    merged.setdefault("profile", profile)
    merged.setdefault(
        "system_prompt_path", str(root / "profiles" / profile / "prompts" / "system_prompt.txt")
    )

    # configs/security.yaml is loaded and validated separately, then folded in. Environment
    # overrides reach it through the same SRAG_SECURITY__* path as everything else.
    merged["security"] = load_security_settings(
        root, overrides=merged.get("security") if isinstance(merged.get("security"), dict) else None
    ).model_dump()

    settings = Settings.model_validate(merged)
    # Anchor relative paths to the repository root, not the launch directory.
    return settings.model_copy(update={"storage": settings.storage.resolve(root)})
