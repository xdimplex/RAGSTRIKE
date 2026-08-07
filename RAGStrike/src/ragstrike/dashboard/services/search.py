"""Global search across reports, plugins, targets, scan history, and findings.

WHY IT SCORES INSTEAD OF JUST MATCHING
    Typing "prompt" matches a plugin named ``prompt-injection``, a finding whose title contains the
    word, and three scans that ran that plugin. Presented unranked, the exact match is buried. The
    scoring is intentionally simple -- exact identifier beats prefix beats substring, and each kind
    carries a small weight -- because a search that ranks by something the operator cannot predict
    is worse than one that ranks obviously.

WHY IT DEGRADES PER SOURCE
    Each source is queried independently and a source that fails contributes nothing rather than
    failing the search. With a partially available backend, searching for a target you can see on
    screen should still find it, even if the reports endpoint is down.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from ragstrike.dashboard.services.errors import DashboardError
from ragstrike.dashboard.services.models import SearchHit

#: Per-kind weight. Targets and plugins rank above history because they are things you *act* on,
#: and a search box is usually a navigation shortcut rather than a query.
KIND_WEIGHT: dict[str, float] = {
    "target": 1.0,
    "plugin": 0.95,
    "report": 0.85,
    "scan": 0.8,
    "finding": 0.75,
}

#: Which page a hit navigates to.
KIND_PAGE: dict[str, str] = {
    "target": "targets",
    "plugin": "plugins",
    "report": "reports",
    "scan": "scan_history",
    "finding": "scan_history",
}

#: Below this, a hit is noise. Tuned so a bare substring match still appears but ranks last.
MIN_SCORE = 0.2


def score(needle: str, *fields: str) -> float:
    """How well a query matches a row, 0.0-1.0.

    Exact match on any field is 1.0; a prefix is 0.7; a substring is 0.4; anything else is 0.0.
    Deliberately not fuzzy: a security tool that "helpfully" returns the wrong finding for a typo is
    worse than one that returns nothing and lets you retype.
    """
    query = needle.strip().lower()
    if not query:
        return 0.0
    best = 0.0
    for raw in fields:
        value = raw.strip().lower()
        if not value:
            continue
        if value == query:
            return 1.0
        if value.startswith(query):
            best = max(best, 0.7)
        elif query in value:
            best = max(best, 0.4)
    return best


@dataclass(frozen=True, slots=True)
class SearchSource:
    """One searchable collection, described so :func:`search` needs no branch per kind."""

    kind: str
    #: Called with no arguments; returns the rows. May raise -- the caller absorbs it.
    fetch: Callable[[], Iterable[object]]
    #: Attributes to match against, in priority order.
    fields: Sequence[str]
    #: Attributes used for the result title and subtitle.
    title_field: str
    subtitle_field: str = ""
    id_field: str = "id"


def _text(item: object, name: str) -> str:
    value = getattr(item, name, "")
    return "" if value is None else str(value)


def search(query: str, sources: Sequence[SearchSource], *, limit: int = 20) -> list[SearchHit]:
    """Search every source and return ranked hits."""
    if not query.strip():
        return []

    hits: list[SearchHit] = []
    for source in sources:
        try:
            rows = list(source.fetch())
        except DashboardError:
            continue  # this source is unavailable; the others still answer
        for row in rows:
            raw = score(query, *(_text(row, name) for name in source.fields))
            if raw <= 0.0:
                continue
            weighted = raw * KIND_WEIGHT.get(source.kind, 0.5)
            if weighted < MIN_SCORE:
                continue
            hits.append(
                SearchHit(
                    kind=source.kind,
                    id=_text(row, source.id_field),
                    title=_text(row, source.title_field) or _text(row, source.id_field),
                    subtitle=_text(row, source.subtitle_field) if source.subtitle_field else "",
                    page_id=KIND_PAGE.get(source.kind, "home"),
                    score=weighted,
                )
            )

    hits.sort(key=lambda hit: (-hit.score, hit.kind, hit.title.lower()))
    return hits[:limit]


def group_by_kind(hits: Sequence[SearchHit]) -> list[tuple[str, list[SearchHit]]]:
    """Hits bucketed by kind, in :data:`KIND_WEIGHT` order, for a sectioned results panel."""
    buckets: list[tuple[str, list[SearchHit]]] = []
    for kind in KIND_WEIGHT:
        members = [hit for hit in hits if hit.kind == kind]
        if members:
            buckets.append((kind, members))
    return buckets
