"""Tests for the pure sdk/utils modules: StringUtils, FormattingUtils."""

from __future__ import annotations

from ragstrike.sdk.utils import FormattingUtils, StringUtils

# -- StringUtils ----------------------------------------------------------------------------------


def test_truncate_leaves_short_text_unchanged() -> None:
    assert StringUtils.truncate("hi", 10) == "hi"


def test_truncate_cuts_long_text_and_appends_suffix() -> None:
    result = StringUtils.truncate("x" * 20, 10)

    assert len(result) == 10
    assert result.endswith("…")


def test_truncate_zero_or_negative_length_returns_empty() -> None:
    assert StringUtils.truncate("hello", 0) == ""
    assert StringUtils.truncate("hello", -5) == ""


def test_truncate_suffix_longer_than_length_is_still_bounded() -> None:
    result = StringUtils.truncate("hello world", 2, suffix="…")

    assert len(result) == 2


def test_normalize_whitespace_collapses_and_strips() -> None:
    assert StringUtils.normalize_whitespace("  a\n\tb   c  ") == "a b c"


def test_contains_any_case_sensitive_by_default() -> None:
    assert StringUtils.contains_any("Hello World", "World") is True
    assert StringUtils.contains_any("Hello World", "world") is False


def test_contains_any_case_insensitive() -> None:
    assert StringUtils.contains_any("Hello World", "world", case_sensitive=False) is True


def test_contains_all_requires_every_needle() -> None:
    assert StringUtils.contains_all("the quick brown fox", "quick", "fox") is True
    assert StringUtils.contains_all("the quick brown fox", "quick", "slow") is False


def test_slugify_lowercases_and_hyphenates() -> None:
    assert StringUtils.slugify("My Attack Name!") == "my-attack-name"


def test_slugify_strips_leading_and_trailing_hyphens() -> None:
    assert StringUtils.slugify("  --Weird--  ") == "weird"


def test_slugify_ascii_folds_accented_characters() -> None:
    assert StringUtils.slugify("Café Déjà Vu") == "cafe-deja-vu"


# -- FormattingUtils --------------------------------------------------------------------------


def test_human_duration_under_a_second() -> None:
    assert FormattingUtils.human_duration(350) == "350ms"


def test_human_duration_seconds() -> None:
    assert FormattingUtils.human_duration(1500) == "1.5s"


def test_human_duration_minutes_and_seconds() -> None:
    assert FormattingUtils.human_duration(65000) == "1m 5s"


def test_human_bytes_under_one_kb() -> None:
    assert FormattingUtils.human_bytes(512) == "512 B"


def test_human_bytes_kb() -> None:
    assert FormattingUtils.human_bytes(1536) == "1.5 KB"


def test_human_bytes_mb() -> None:
    assert FormattingUtils.human_bytes(5 * 1024 * 1024) == "5.0 MB"


def test_human_bytes_caps_at_largest_unit() -> None:
    huge = 10 * 1024**5  # far past TB
    result = FormattingUtils.human_bytes(huge)

    assert result.endswith("TB")


def test_percentage_default_precision() -> None:
    assert FormattingUtils.percentage(0.4567) == "45.7%"


def test_percentage_custom_precision() -> None:
    assert FormattingUtils.percentage(0.4567, decimals=0) == "46%"
    assert FormattingUtils.percentage(0.5, decimals=2) == "50.00%"
