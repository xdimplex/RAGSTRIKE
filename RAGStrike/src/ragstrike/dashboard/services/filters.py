"""Filtering and sorting, once, for every list in the product.

WHY ONE IMPLEMENTATION
    The brief asks for filtering by severity, plugin, target, date, category, status, and risk score
    -- on findings, on scans, on reports, and on plugins. Four pages implementing the same seven
    predicates is four chances for "severity: HIGH" to mean something slightly different in one of
    them. It is written once here and the pages pass their rows through it.

HOW IT MATCHES
    By attribute name, not by type. A row is included if every *active* facet matches; an empty
    facet means "no constraint" rather than "match nothing", which is the behaviour an operator
    expects from an untouched filter panel. Rows that simply do not have an attribute are not
    excluded by a facet that names it -- a reports list has no ``category``, and filtering by
    category there should be a no-op rather than an empty page.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Any, TypeVar

from ragstrike.dashboard.services.models import parse_timestamp

T = TypeVar("T")

#: Severity order, worst first. Used for sorting and for the "at least this severe" comparison --
#: alphabetical order would put CRITICAL after both HIGH and INFO, which is exactly backwards.
SEVERITY_ORDER: tuple[str, ...] = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")

_SEVERITY_RANK = {name: index for index, name in enumerate(SEVERITY_ORDER)}

#: The risk scale is 0-100 (SDD 17.3). A filter spanning the whole range is no filter at all.
MAX_RISK = 100.0


def severity_rank(severity: str) -> int:
    """Rank a severity, worst = 0. Unknown severities sort last rather than first."""
    return _SEVERITY_RANK.get(severity.strip().upper(), len(SEVERITY_ORDER))


@dataclass(frozen=True, slots=True)
class FilterState:
    """One filter panel's selections.

    Frozen: the panel produces a new state on change, so a half-applied filter can never be observed
    partway through a render.
    """

    text: str = ""
    severities: tuple[str, ...] = ()
    plugins: tuple[str, ...] = ()
    targets: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()
    date_from: str = ""
    date_to: str = ""
    min_risk: float = 0.0
    max_risk: float = MAX_RISK

    @property
    def active(self) -> bool:
        """Whether anything is constrained. Drives the "N filters active -- clear" affordance."""
        return bool(
            self.text
            or self.severities
            or self.plugins
            or self.targets
            or self.categories
            or self.statuses
            or self.date_from
            or self.date_to
            or self.min_risk > 0.0
            or self.max_risk < MAX_RISK
        )

    def cleared(self) -> FilterState:
        return FilterState()

    def with_text(self, text: str) -> FilterState:
        return replace(self, text=text)


def _attr(item: object, name: str) -> Any:
    return getattr(item, name, None)


def _in_set(item: object, name: str, allowed: Sequence[str]) -> bool:
    if not allowed:
        return True
    value = _attr(item, name)
    if value is None:
        return True  # the row has no such field; the facet does not apply to it
    return str(value).strip().upper() in {a.strip().upper() for a in allowed}


def _text_match(item: object, needle: str, fields: Sequence[str]) -> bool:
    if not needle:
        return True
    lowered = needle.strip().lower()
    for name in fields:
        value = _attr(item, name)
        if value is not None and lowered in str(value).lower():
            return True
    return False


#: Attributes free-text search looks at. Chosen rather than "every attribute" so that typing "html"
#: does not match a report because its id happens to contain the letters.
TEXT_FIELDS: tuple[str, ...] = (
    "id",
    "name",
    #: A report is labelled by the scan it covers, so the search box on the Reports page has to look
    #: there too -- otherwise the name shown in every row is the one thing that cannot be searched.
    "scan_name",
    "slug",
    "title",
    "target",
    "plugin",
    "category",
    "description",
    "recommendation",
    "profile",
)


def _date_match(item: object, state: FilterState) -> bool:
    if not (state.date_from or state.date_to):
        return True
    raw = ""
    for name in ("timestamp", "generated_at", "started_at", "checked_at"):
        value = _attr(item, name)
        if value:
            raw = str(value)
            break
    stamp = parse_timestamp(raw)
    if stamp is None:
        return True  # undated rows are not evidence of being outside the window
    if state.date_from and stamp.date().isoformat() < state.date_from:
        return False
    return not (state.date_to and stamp.date().isoformat() > state.date_to)


def _risk_match(item: object, state: FilterState) -> bool:
    if state.min_risk <= 0.0 and state.max_risk >= MAX_RISK:
        return True
    value = _attr(item, "risk_score")
    if value is None:
        return True
    return state.min_risk <= float(value) <= state.max_risk


def matches(item: object, state: FilterState) -> bool:
    """Whether one row survives every active facet."""
    return (
        _text_match(item, state.text, TEXT_FIELDS)
        and _in_set(item, "severity", state.severities)
        and _plugin_match(item, state.plugins)
        and _in_set(item, "target", state.targets)
        and _in_set(item, "category", state.categories)
        and _status_match(item, state.statuses)
        and _date_match(item, state)
        and _risk_match(item, state)
    )


def _plugin_match(item: object, allowed: Sequence[str]) -> bool:
    """Plugins are named ``plugin`` on a finding and ``slug`` on a plugin row.

    Both are checked, and a row that has neither is not excluded -- otherwise selecting a plugin on
    a page whose rows are targets would empty the page.
    """
    if not allowed:
        return True
    wanted = {a.strip().lower() for a in allowed}
    for name in ("plugin", "slug"):
        value = _attr(item, name)
        if value is not None:
            return str(value).strip().lower() in wanted
    return True


def _status_match(item: object, allowed: Sequence[str]) -> bool:
    """Status lives under ``status``, ``state``, or ``outcome`` depending on the row type."""
    if not allowed:
        return True
    wanted = {a.strip().upper() for a in allowed}
    for name in ("status", "state", "outcome"):
        value = _attr(item, name)
        if value:
            return str(value).strip().upper() in wanted
    return True


def apply_filters(items: Iterable[T], state: FilterState) -> list[T]:
    """Filter a sequence, preserving order."""
    return [item for item in items if matches(item, state)]


#: Sort keys the tables offer, mapped to the accessor that produces a comparable value.
SORT_KEYS: dict[str, Callable[[Any], Any]] = {
    "severity": lambda item: severity_rank(str(getattr(item, "severity", ""))),
    "risk": lambda item: float(getattr(item, "risk_score", 0.0) or 0.0),
    "date": lambda item: str(
        getattr(item, "timestamp", "")
        or getattr(item, "generated_at", "")
        or getattr(item, "started_at", "")
    ),
    "name": lambda item: str(
        getattr(item, "name", "") or getattr(item, "title", "") or getattr(item, "id", "")
    ).lower(),
    "target": lambda item: str(getattr(item, "target", "")).lower(),
    "confidence": lambda item: float(getattr(item, "confidence", 0.0) or 0.0),
}


def sort_items(items: Iterable[T], key: str, *, descending: bool = True) -> list[T]:
    """Sort by one of :data:`SORT_KEYS`. An unknown key leaves the order untouched.

    Leaving it untouched is deliberate: the backend already returns rows in a meaningful order
    (newest first), and silently re-sorting by a key that does not exist would look like a bug in
    the backend rather than in the sort selector.
    """
    accessor = SORT_KEYS.get(key)
    if accessor is None:
        return list(items)
    # Severity ranks worst = 0, so "descending" (most severe first) is an ascending sort on rank.
    reverse = descending if key != "severity" else not descending
    return sorted(items, key=accessor, reverse=reverse)
