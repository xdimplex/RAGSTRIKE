"""Global search tests.

THE CLAIM UNDER TEST: **search ranks predictably and degrades per source.**

Typing "prompt" matches a plugin named ``prompt-injection``, several findings, and every scan that
ran it. Presented unranked, the exact match is buried. And with a partially available backend,
searching for a target visible on screen must still find it even if the reports endpoint is down --
otherwise a search box becomes the least reliable way to navigate.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ragstrike.dashboard.services import build_services_with
from ragstrike.dashboard.services.demo import DemoTransport
from ragstrike.dashboard.services.errors import BackendUnavailableError
from ragstrike.dashboard.services.search import (
    KIND_PAGE,
    KIND_WEIGHT,
    MIN_SCORE,
    SearchSource,
    group_by_kind,
    score,
    search,
)


@dataclass(frozen=True)
class Row:
    id: str
    name: str = ""
    category: str = ""


def source(kind: str, rows: list[Row], **overrides: object) -> SearchSource:
    defaults: dict[str, object] = {
        "kind": kind,
        "fetch": lambda: rows,
        "fields": ("id", "name", "category"),
        "title_field": "name",
        "subtitle_field": "category",
    }
    defaults.update(overrides)
    return SearchSource(**defaults)  # type: ignore[arg-type]  # keyword construction from a mapping


# -- scoring ---------------------------------------------------------------------------------------


def test_an_exact_match_outranks_a_prefix_which_outranks_a_substring() -> None:
    """The ordering an operator can predict without reading the source."""
    assert score("prompt", "prompt") > score("prompt", "prompt-injection")
    assert score("prompt", "prompt-injection") > score("prompt", "system-prompt-leak")


def test_a_non_match_scores_zero() -> None:
    assert score("prompt", "context-poisoning") == 0.0


def test_an_empty_query_scores_zero() -> None:
    """Otherwise an empty search box would match everything and render the whole database."""
    assert score("", "anything") == 0.0
    assert score("   ", "anything") == 0.0


def test_matching_is_case_insensitive() -> None:
    assert score("PROMPT", "prompt-injection") == score("prompt", "PROMPT-INJECTION")


def test_the_best_field_wins() -> None:
    """A row matching exactly on its second field should not be penalised for its first."""
    assert score("beta", "alpha", "beta") == 1.0


def test_search_is_not_fuzzy() -> None:
    """A security tool that helpfully returns the wrong finding for a typo is worse than one that
    returns nothing and lets you retype."""
    assert score("promt", "prompt-injection") == 0.0


# -- ranking ---------------------------------------------------------------------------------------


def test_results_are_ordered_by_score() -> None:
    rows = [Row(id="a", name="system-prompt-leak"), Row(id="b", name="prompt")]

    hits = search("prompt", [source("plugin", rows)])

    assert [hit.title for hit in hits] == ["prompt", "system-prompt-leak"]


def test_kind_weight_breaks_ties_between_equal_matches() -> None:
    """Targets and plugins outrank history because they are things you *act* on -- a search box is
    usually a navigation shortcut."""
    sources = [
        source("scan", [Row(id="prompt", name="prompt")]),
        source("target", [Row(id="prompt", name="prompt")]),
    ]

    hits = search("prompt", sources)

    assert hits[0].kind == "target"


def test_weak_matches_are_dropped() -> None:
    """Below the threshold a hit is noise -- it pushes the answer off the visible list."""
    weakest = min(KIND_WEIGHT.values()) * 0.4

    hits = search("t", [source("finding", [Row(id="x", name="a very long unrelated title")])])

    assert weakest >= MIN_SCORE or hits == []


def test_the_limit_is_honoured() -> None:
    rows = [Row(id=f"prompt-{i}", name=f"prompt-{i}") for i in range(30)]

    assert len(search("prompt", [source("plugin", rows)], limit=5)) == 5


def test_ordering_is_stable_for_equally_scored_hits() -> None:
    """An unstable order makes the results list appear to shuffle between keystrokes."""
    rows = [Row(id="b", name="prompt-b"), Row(id="a", name="prompt-a")]

    first = [h.title for h in search("prompt", [source("plugin", rows)])]
    second = [h.title for h in search("prompt", [source("plugin", rows)])]

    assert first == second


# -- degradation -----------------------------------------------------------------------------------


def test_a_failing_source_contributes_nothing_rather_than_failing_the_search() -> None:
    """With a partially available backend, searching for a target you can see on screen must still
    find it."""

    def explode() -> list[Row]:
        raise BackendUnavailableError("reports endpoint is down")

    sources = [
        SearchSource(
            kind="report",
            fetch=explode,
            fields=("id",),
            title_field="id",
        ),
        source("target", [Row(id="vulnerable-rag", name="vulnerable-rag")]),
    ]

    hits = search("vulnerable", sources)

    assert [hit.kind for hit in hits] == ["target"]


def test_an_empty_query_returns_nothing_without_touching_a_source() -> None:
    """A search box the operator has not typed in should not fetch five collections on every
    re-run."""
    touched: list[str] = []

    def record() -> list[Row]:
        touched.append("fetched")
        return []

    search("", [SearchSource(kind="target", fetch=record, fields=("id",), title_field="id")])

    assert touched == []


# -- navigation ------------------------------------------------------------------------------------


def test_every_searchable_kind_knows_where_to_navigate() -> None:
    """A hit with nowhere to go is a result the operator cannot act on."""
    assert set(KIND_WEIGHT) <= set(KIND_PAGE)


@pytest.mark.parametrize("kind", sorted(KIND_PAGE))
def test_every_destination_is_a_real_page(kind: str) -> None:
    from ragstrike.dashboard.navigation.routes import ROUTES

    assert KIND_PAGE[kind] in {route.id for route in ROUTES}


def test_a_hit_carries_its_destination() -> None:
    hits = search("prompt", [source("plugin", [Row(id="p", name="prompt")])])

    assert hits[0].page_id == "plugins"


# -- grouping --------------------------------------------------------------------------------------


def test_hits_group_by_kind_in_weight_order() -> None:
    sources = [
        source("scan", [Row(id="prompt-scan", name="prompt-scan")]),
        source("target", [Row(id="prompt-target", name="prompt-target")]),
    ]

    groups = [kind for kind, _ in group_by_kind(search("prompt", sources))]

    assert groups == ["target", "scan"]


def test_empty_groups_are_omitted() -> None:
    hits = search("prompt", [source("plugin", [Row(id="p", name="prompt")])])

    assert [kind for kind, _ in group_by_kind(hits)] == ["plugin"]


# -- against the real service wiring ---------------------------------------------------------------


def test_the_shipped_sources_cover_the_collections_the_brief_names() -> None:
    """Reports, plugins, targets, and scan history. Findings are reached through their scan, which
    is what the scan hit navigates to."""
    kinds = {s.kind for s in build_services_with(DemoTransport()).search_sources()}

    assert {"report", "plugin", "target", "scan"} <= kinds


def test_searching_the_real_wiring_finds_a_plugin_by_slug() -> None:
    container = build_services_with(DemoTransport())

    hits = search("prompt-injection", container.search_sources())

    assert any(hit.kind == "plugin" and hit.id == "prompt-injection" for hit in hits)


def test_searching_the_real_wiring_finds_a_target_by_name() -> None:
    container = build_services_with(DemoTransport())

    hits = search("secure-rag", container.search_sources())

    assert any(hit.kind == "target" and hit.id == "secure-rag" for hit in hits)


def test_a_query_matching_nothing_returns_nothing() -> None:
    container = build_services_with(DemoTransport())

    assert search("zzzzzzz", container.search_sources()) == []
