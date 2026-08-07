"""SdkPayloadLoader tests.

The property under test that matters most: one malformed file must never affect another file's
result, and must never abort the whole load. Contrast with
``tests/unit/test_payload_loader.py``, which tests the Phase 4 *strict* loader that this one
wraps -- that one is expected to raise on the first bad file; this one is expected not to.
"""

from __future__ import annotations

from pathlib import Path

from ragstrike.sdk.payload_loader import SdkPayloadLoader


def test_missing_directory_yields_empty_result(tmp_path: Path) -> None:
    result = SdkPayloadLoader(tmp_path / "does-not-exist").load()

    assert result.payloads == []
    assert result.skipped == []
    assert result.ok


def test_loads_valid_yaml(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("- id: p1\n  content: hello\n", encoding="utf-8")

    result = SdkPayloadLoader(tmp_path).load()

    assert [p.id for p in result.payloads] == ["p1"]
    assert result.ok


def test_loads_json_and_txt_alongside_yaml(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("- id: y1\n  content: from-yaml\n", encoding="utf-8")
    (tmp_path / "b.json").write_text('[{"id": "j1", "content": "from-json"}]', encoding="utf-8")
    (tmp_path / "c.txt").write_text("from-txt\n", encoding="utf-8")

    result = SdkPayloadLoader(tmp_path).load()

    assert {p.content for p in result.payloads} == {"from-yaml", "from-json", "from-txt"}


def test_a_malformed_file_is_skipped_not_fatal(tmp_path: Path) -> None:
    """The defining property. A strict loader would raise here; this one must not."""
    (tmp_path / "good.yaml").write_text("- id: g1\n  content: fine\n", encoding="utf-8")
    (tmp_path / "bad.yaml").write_text("- id: b1\n  content: [unclosed\n", encoding="utf-8")

    result = SdkPayloadLoader(tmp_path).load()

    assert [p.id for p in result.payloads] == ["g1"]
    assert len(result.skipped) == 1
    assert result.skipped[0].path.name == "bad.yaml"
    assert not result.ok


def test_a_file_that_sorts_before_the_bad_one_is_unaffected(tmp_path: Path) -> None:
    """Regression guard: the naive implementation (rescanning the whole directory per file)
    mislabels files that sort AFTER a bad one -- this checks the file that sorts BEFORE, which
    the naive bug would also have gotten right by accident, and the AFTER case below, which it
    would not."""
    (tmp_path / "1_bad.yaml").write_text("content: [unclosed\n", encoding="utf-8")
    (tmp_path / "2_good.yaml").write_text("- id: g1\n  content: fine\n", encoding="utf-8")

    result = SdkPayloadLoader(tmp_path).load()

    assert [p.id for p in result.payloads] == ["g1"]
    assert [s.path.name for s in result.skipped] == ["1_bad.yaml"]


def test_multiple_malformed_files_are_all_recorded_independently(tmp_path: Path) -> None:
    (tmp_path / "bad1.yaml").write_text("[unclosed\n", encoding="utf-8")
    (tmp_path / "bad2.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "good.yaml").write_text("- id: g1\n  content: fine\n", encoding="utf-8")

    result = SdkPayloadLoader(tmp_path).load()

    assert len(result.payloads) == 1
    assert {s.path.name for s in result.skipped} == {"bad1.yaml", "bad2.json"}


def test_unsupported_extensions_are_ignored_not_skipped(tmp_path: Path) -> None:
    """A README next to the payloads must not appear as a "skipped" file -- it was never a
    candidate in the first place."""
    (tmp_path / "README.md").write_text("not a payload", encoding="utf-8")
    (tmp_path / "a.yaml").write_text("- id: g1\n  content: fine\n", encoding="utf-8")

    result = SdkPayloadLoader(tmp_path).load()

    assert result.skipped == []


def test_all_returns_just_the_successful_payloads(tmp_path: Path) -> None:
    (tmp_path / "good.yaml").write_text("- id: g1\n  content: fine\n", encoding="utf-8")
    (tmp_path / "bad.yaml").write_text("[unclosed\n", encoding="utf-8")

    assert [p.id for p in SdkPayloadLoader(tmp_path).all()] == ["g1"]


def test_filename_order_is_preserved(tmp_path: Path) -> None:
    for name in ("c.yaml", "a.yaml", "b.yaml"):
        (tmp_path / name).write_text(f"- id: {name}\n  content: x\n", encoding="utf-8")

    assert [p.id for p in SdkPayloadLoader(tmp_path).all()] == ["a.yaml", "b.yaml", "c.yaml"]
