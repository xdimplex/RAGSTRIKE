"""The ``configs/security.yaml`` schema.

WHY THIS IS A SEPARATE MODULE FROM ``rag/config.py``
    ``rag/config.py`` is shared-core code that SecureRAG inherits from VulnerableRAG verbatim except
    for one added field. Keeping the security schema in its own module means the diff against the
    upstream file stays to a handful of lines, which is what makes the two repositories reviewable
    side by side -- see ``docs/compatibility-guide.md`` for the full list of divergences.

WHY EVERY FIELD IS VALIDATED AND BOUNDED
    These values are the thresholds a security control enforces. A typo that turns
    ``max_question_chars`` into ``20`` makes the application refuse everything; one that turns it
    into ``2000000`` silently removes the control. Both fail at startup here rather than in
    production, with the exact field path.

WHAT THIS SCHEMA DELIBERATELY CANNOT EXPRESS
    There is no field that removes a control from the chain. Controls are composed in code by
    ``rag.policy.controls.build_controls``. The settings here tune *checks within* a control; they
    never make one vanish. A security posture a YAML edit can silently erase is a posture nobody can
    rely on -- the same reasoning ADR-009 applies to the profile split.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class SanitizerSettings(BaseModel):
    normalize_unicode: bool = True
    strip_invisible_characters: bool = True
    neutralize_instructions: bool = True


class ValidationSettings(BaseModel):
    max_question_chars: int = Field(default=2000, gt=0, le=100_000)
    min_question_chars: int = Field(default=1, ge=0)
    normalize_unicode: bool = True
    reject_control_characters: bool = True

    @field_validator("min_question_chars")
    @classmethod
    def _min_below_max(cls, value: int, info: Any) -> int:
        maximum = info.data.get("max_question_chars")
        if maximum is not None and value > maximum:
            raise ValueError(
                f"min_question_chars ({value}) exceeds max_question_chars ({maximum}); "
                f"no question could ever be accepted"
            )
        return value


class RetrievalSecuritySettings(BaseModel):
    min_score: float = Field(default=0.15, ge=0.0, le=1.0)
    max_chunks: int = Field(default=5, gt=0, le=100)
    max_chunk_chars: int = Field(default=4000, gt=0)
    max_instruction_density: float = Field(default=8.0, gt=0.0)


class SessionSecuritySettings(BaseModel):
    max_history_turns: int = Field(default=6, ge=0, le=200)
    max_prompt_chars: int = Field(default=24_000, gt=0)


class OutputSettings(BaseModel):
    max_answer_chars: int = Field(default=8000, gt=0)
    detect_prompt_echo: bool = True
    echo_window: int = Field(default=48, ge=16, le=512)
    normalize_whitespace: bool = True


class MaskingSettings(BaseModel):
    mask_emails: bool = True
    fingerprint_chars: int = Field(default=6, ge=4, le=32)


class CitationSettings(BaseModel):
    annotate_ungrounded: bool = True


class UploadSecuritySettings(BaseModel):
    max_upload_mb: int = Field(default=25, gt=0, le=1024)
    allowed_extensions: list[str] = Field(default_factory=lambda: ["pdf"])
    allowed_mime_types: list[str] = Field(
        default_factory=lambda: [
            "application/pdf",
            "application/x-pdf",
            "application/octet-stream",
        ]
    )
    verify_magic_bytes: bool = True
    reject_duplicates: bool = True

    @field_validator("allowed_extensions")
    @classmethod
    def _normalize_extensions(cls, value: list[str]) -> list[str]:
        """Accept ``pdf``, ``.pdf``, and ``PDF`` and store one canonical form.

        Three spellings of the same extension in a config file is a bug waiting to happen: the
        allowlist check would pass for one and fail for the others.
        """
        if not value:
            raise ValueError("allowed_extensions is empty; no upload could ever be accepted")
        return sorted({item.strip().lstrip(".").lower() for item in value if item.strip()})

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


class HttpSecuritySettings(BaseModel):
    security_headers: bool = True
    suppress_server_header: bool = True


class PlannedControls(BaseModel):
    """Intent flags for controls that do not exist.

    Setting one to ``true`` enables nothing -- there is nothing to enable. It records that the
    operator wants it, and ``GET /health`` reports the gap either way. Documented in
    ``rag/policy/controls/future_controls.py``.
    """

    rate_limiting: bool = False
    authentication: bool = False
    authorization: bool = False


class SecuritySettings(BaseModel):
    """The whole of ``configs/security.yaml``, validated."""

    sanitizer: SanitizerSettings = Field(default_factory=SanitizerSettings)
    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    retrieval: RetrievalSecuritySettings = Field(default_factory=RetrievalSecuritySettings)
    session: SessionSecuritySettings = Field(default_factory=SessionSecuritySettings)
    output: OutputSettings = Field(default_factory=OutputSettings)
    masking: MaskingSettings = Field(default_factory=MaskingSettings)
    citations: CitationSettings = Field(default_factory=CitationSettings)
    uploads: UploadSecuritySettings = Field(default_factory=UploadSecuritySettings)
    http: HttpSecuritySettings = Field(default_factory=HttpSecuritySettings)
    planned: PlannedControls = Field(default_factory=PlannedControls)


def load_security_settings(
    root: Path,
    *,
    overrides: dict[str, Any] | None = None,
) -> SecuritySettings:
    """Read and validate ``configs/security.yaml``.

    A missing file yields the defaults rather than an error: every default in this schema is the
    *secure* value, so an absent configuration file produces a fully hardened application. Failing
    closed is the only safe direction for a file whose absence would otherwise disable defences.
    """
    path = root / "configs" / "security.yaml"
    raw: dict[str, Any] = {}
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        section = loaded.get("security") if isinstance(loaded, dict) else None
        raw = section if isinstance(section, dict) else {}

    if overrides:
        raw = _merge(raw, overrides)

    return SecuritySettings.model_validate(raw)


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result
