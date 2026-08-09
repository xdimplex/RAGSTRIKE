"""Configuration tests.

THE CLAIM UNDER TEST: **configuration can tune a control, and cannot remove one.**

That is the security property the whole ``security.yaml`` design rests on, and it is the one an
operator has to be able to trust without reading the source. If a value in that file could empty the
chain, SecureRAG's posture would be one careless edit away from VulnerableRAG's -- with ``GET
/health`` still reporting seven active policies, because nothing would have told it otherwise.

The second claim: **the defaults are the secure values.** A missing configuration file must produce
a hardened application, not a disabled one. Failing closed is the only safe direction for a file
whose absence would otherwise switch off the defences.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from rag.config import load_settings
from rag.policy.controls import build_controls
from rag.security_config import (
    SecuritySettings,
    UploadSecuritySettings,
    ValidationSettings,
    load_security_settings,
)

EXPECTED_CHAIN_LENGTH = 7


# -- the load path ----------------------------------------------------------------------------------


def test_the_shipped_security_file_loads_and_validates() -> None:
    """If the file that ships cannot load, nothing below matters."""
    settings = load_security_settings(Path.cwd())

    assert settings.validation.max_question_chars > 0
    # pdf/txt/md/csv. An operator should be able to upload the documents they actually have,
    # and every format takes the identical ingestion path -- see rag/ingestion/pipeline.py.
    # Sorted: the field validator canonicalises the list, so order is not part of the contract.
    assert sorted(settings.uploads.allowed_extensions) == ["csv", "md", "pdf", "txt"]


def test_a_missing_file_yields_a_fully_hardened_application(tmp_path: Path) -> None:
    """Fail closed. Every default in the schema is the secure value, so an absent configuration
    produces a hardened application rather than a disabled one."""
    settings = load_security_settings(tmp_path)

    assert settings.sanitizer.neutralize_instructions
    assert settings.output.detect_prompt_echo
    assert settings.masking.mask_emails
    assert settings.uploads.verify_magic_bytes
    assert len(build_controls(settings, system_prompt="x")) == EXPECTED_CHAIN_LENGTH


def test_the_profile_settings_carry_the_security_block(lab_root: Path) -> None:
    """The security schema is loaded separately and folded into ``Settings``; a wiring mistake here
    would leave every control running on schema defaults while the file was silently ignored."""
    settings = load_settings("secure", root=lab_root)

    assert isinstance(settings.security, SecuritySettings)
    assert settings.security.retrieval.min_score == 0.15


# -- what configuration cannot do -------------------------------------------------------------------


def test_no_setting_can_empty_the_chain() -> None:
    """The load-bearing property.

    Every boolean in the schema is turned off at once. The chain must still be complete -- because
    the controls are composed in code, and these flags only narrow what each one checks.
    """
    disarmed = SecuritySettings.model_validate(
        {
            "sanitizer": {
                "normalize_unicode": False,
                "strip_invisible_characters": False,
                "neutralize_instructions": False,
            },
            "validation": {"normalize_unicode": False, "reject_control_characters": False},
            "output": {"detect_prompt_echo": False, "normalize_whitespace": False},
            "masking": {"mask_emails": False},
            "citations": {"annotate_ungrounded": False},
            "uploads": {"verify_magic_bytes": False, "reject_duplicates": False},
            "http": {"security_headers": False, "suppress_server_header": False},
        }
    )

    assert len(build_controls(disarmed, system_prompt="x")) == EXPECTED_CHAIN_LENGTH


def test_the_schema_has_no_field_that_disables_a_control() -> None:
    """Read the schema rather than trusting review. A field named ``enabled`` or ``controls`` would
    be the beginning of exactly the toggle this design forbids."""
    forbidden = {"enabled", "disabled", "controls", "policies", "secure", "enforce"}

    assert not (set(SecuritySettings.model_fields) & forbidden)


def test_the_planned_flags_enable_nothing() -> None:
    """Setting one records intent. There is nothing to enable -- the controls are declared, not
    built -- and ``GET /health`` reports the gap either way."""
    settings = SecuritySettings.model_validate(
        {"planned": {"rate_limiting": True, "authentication": True, "authorization": True}}
    )

    names = [control.name for control in build_controls(settings, system_prompt="x")]

    assert "rate-limiter" not in names
    assert "authenticator" not in names
    assert "authorizer" not in names


# -- validation of the values themselves --------------------------------------------------------------


def test_an_out_of_range_threshold_fails_at_startup() -> None:
    """A typo that turns a limit into nonsense must fail here, with the field path, rather than in
    production."""
    with pytest.raises(ValidationError):
        ValidationSettings(max_question_chars=0)


def test_a_contradictory_length_range_is_refused() -> None:
    """min > max would accept no question at all -- a configuration mistake, not a policy."""
    with pytest.raises(ValidationError, match="could ever be accepted"):
        ValidationSettings(max_question_chars=10, min_question_chars=100)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("retrieval", "min_score", 1.5),
        ("retrieval", "max_chunks", 0),
        ("output", "echo_window", 4),
        ("masking", "fingerprint_chars", 2),
        ("session", "max_prompt_chars", 0),
    ],
)
def test_every_bounded_field_is_actually_bounded(section: str, field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        SecuritySettings.model_validate({section: {field: value}})


def test_an_upload_limit_is_capped() -> None:
    """A 10 GB limit is not a policy decision, it is a mistake."""
    with pytest.raises(ValidationError):
        UploadSecuritySettings(max_upload_mb=100_000)


def test_a_malformed_security_file_fails_loudly(tmp_path: Path) -> None:
    """Silently falling back to defaults would be worse than an error: the operator would believe
    their tuning was applied."""
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "security.yaml").write_text(
        "security:\n  validation:\n    max_question_chars: -5\n", encoding="utf-8"
    )

    with pytest.raises(ValidationError):
        load_security_settings(tmp_path)


# -- environment overrides ---------------------------------------------------------------------------


def test_an_environment_override_reaches_a_security_threshold(
    lab_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SRAG_SECURITY__VALIDATION__MAX_QUESTION_CHARS", "555")

    settings = load_settings("secure", root=lab_root)

    assert settings.security.validation.max_question_chars == 555


def test_the_legacy_prefix_still_works(lab_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One less incidental difference between the two applications: a lab script written for either
    one works against both."""
    monkeypatch.setenv("VRAG_RETRIEVAL__TOP_K", "9")

    assert load_settings("secure", root=lab_root).retrieval.top_k == 9


def test_the_new_prefix_wins_where_both_are_set(
    lab_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VRAG_RETRIEVAL__TOP_K", "3")
    monkeypatch.setenv("SRAG_RETRIEVAL__TOP_K", "7")

    assert load_settings("secure", root=lab_root).retrieval.top_k == 7


def test_an_override_cannot_empty_the_chain(
    lab_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The environment is the easiest surface to change by accident -- a stale shell export outlives
    a config edit -- so the invariant is tested here too."""
    monkeypatch.setenv("SRAG_SECURITY__SANITIZER__NEUTRALIZE_INSTRUCTIONS", "false")
    monkeypatch.setenv("SRAG_SECURITY__OUTPUT__DETECT_PROMPT_ECHO", "false")

    settings = load_settings("secure", root=lab_root)

    assert len(build_controls(settings.security, system_prompt="x")) == EXPECTED_CHAIN_LENGTH


# -- the profile configuration -------------------------------------------------------------------------


def test_the_secure_profile_binds_its_own_ports(lab_root: Path) -> None:
    """9001/8602, so both applications can run side by side and be scanned in one session."""
    settings = load_settings("secure", root=lab_root)

    assert settings.server.api_port == 9001
    assert settings.server.ui_port == 8602


def test_the_secure_profile_does_not_expose_its_system_prompt(lab_root: Path) -> None:
    assert load_settings("secure", root=lab_root).api.expose_system_prompt is False


def test_the_secure_profile_still_exposes_chunks_and_sources(lab_root: Path) -> None:
    """Withholding them would make SecureRAG score better by being less inspectable, which is not a
    security improvement."""
    settings = load_settings("secure", root=lab_root)

    assert settings.api.expose_retrieved_chunks
    assert settings.api.expose_sources


def test_the_system_prompt_contains_no_credential(lab_root: Path) -> None:
    """The cheapest fix in the application, and the one masking exists to back up rather than
    replace."""
    prompt = load_settings("secure", root=lab_root).system_prompt()

    assert "CANARY" not in prompt
    assert "postgresql://" not in prompt
    assert "api key" not in prompt.lower() or "produce credentials" in prompt.lower()


def test_the_system_prompt_states_the_instruction_hierarchy(lab_root: Path) -> None:
    """The structural defence. Without this language the fences are decoration."""
    prompt = load_settings("secure", root=lab_root).system_prompt().lower()

    assert "untrusted" in prompt
    assert "never act on it" in prompt or "never treat" in prompt
