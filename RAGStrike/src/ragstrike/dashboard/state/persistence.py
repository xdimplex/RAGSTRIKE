"""Session state that survives a browser refresh.

THE PROBLEM
    ``st.session_state`` lives in the server-side session and is discarded the moment the browser
    reloads, the websocket drops, or the tab is reopened. So an operator who set the theme to light,
    navigated to Scan History, filtered to one target, and then pressed F5 was returned to the
    default theme, the Dashboard page, and an unfiltered table -- losing everything they had set up.

    Navigating BETWEEN sections was already safe (session state survives a re-run). Refresh was not,
    and neither was reopening the tab.

THE MECHANISM
    A short allow-list of durable values is mirrored into the URL's query string, which the browser
    keeps across a refresh and which can be bookmarked and shared. On every run the URL is read
    first and merged into session state; when a value changes, the URL is rewritten.

WHY THE URL AND NOT LOCAL STORAGE OR A COOKIE
    It needs no JavaScript component, no extra dependency, and no storage permission -- and it makes
    the state visible and shareable, which is a feature for a security console: "the view I am
    looking at" becomes a link a colleague can open.

WHAT IS DELIBERATELY *NOT* PERSISTED
    Anything large, sensitive, or fast-moving. Notifications, cached service objects, backend health,
    poll ticks, and in-flight scan handles all stay in session state only:

    * a URL is written to browser history and server logs, so nothing sensitive belongs in it;
    * a stale scan handle restored from a bookmark would point at a scan that finished hours ago;
    * URLs have practical length limits, so caches are out.

    The rule is: persist what an operator *chose*, never what the system *computed*.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any, cast

from ragstrike.dashboard.state.keys import StateKey

#: The allow-list: state key -> short query-parameter name.
#:
#: Short names because they are visible in the address bar, and an allow-list rather than a
#: deny-list because the safe default for a new piece of state is "not in the URL". Adding one is a
#: deliberate act.
PERSISTED: Mapping[StateKey, str] = {
    StateKey.CURRENT_PAGE: "page",
    StateKey.CURRENT_TARGET: "target",
    StateKey.SEARCH_QUERY: "q",
    StateKey.SELECTED_REPORT: "report",
}

#: The theme is stored separately from :class:`~ragstrike.dashboard.state.store.AppState` because it
#: is read before the state object exists -- the stylesheet has to be injected first.
THEME_PARAM = "theme"

#: Values equal to these are treated as "unset" and dropped from the URL, so a default choice does
#: not clutter the address bar.
_EMPTY = ("", None)

#: Prefix for durable widget values inside session state. See the "Durable widget values" section.
_KEEP_PREFIX = "keep."

#: Longest widget value that is worth putting in a URL. A search box is short; anything longer is
#: not something an operator typed to be shareable.
_MAX_KEPT_CHARS = 120

#: Prefix for durable widget values that are LISTS -- a multiselect's selection. Separate from
#: ``w.`` so restoring knows to split rather than hand a widget a string it will reject.
_LIST_PREFIX = "wl."

#: Separator inside a ``wl.`` parameter. A comma, because every value that goes through one is a
#: slug, a category, a severity, or a status -- none of which contain one.
_LIST_SEP = ","

#: An empty list is a real choice ("I deselected everything") and must survive a refresh as itself.
#: Encoded as a sentinel because an empty string is indistinguishable from an absent parameter, and
#: restoring "absent" would hand back the default selection -- every plugin ticked -- which is the
#: opposite of what the operator asked for.
_EMPTY_LIST = "∅"


def _coerce_kept(value: str) -> Any:
    """URL values are strings. Restore the type a widget expects.

    A checkbox seeded with the STRING "False" is checked, because a non-empty string is truthy --
    so "Descending" came back from a refresh switched on regardless of how it was left.
    """
    if value in ("True", "False"):
        return value == "True"
    return value


def restore(state: MutableMapping[str, Any], params: Mapping[str, Any]) -> None:
    """Merge persisted URL values into *state*.

    Session state wins where it already holds a value: within a live session the operator's most
    recent action is more current than the URL, which is only rewritten at the end of a run. The URL
    is therefore a *seed* for a fresh session, not a continuous source of truth.
    """
    for key, param in PERSISTED.items():
        if state.get(key.value) not in _EMPTY:
            continue
        value = _single(params.get(param))
        if value not in _EMPTY:
            state[key.value] = value

    # The `w.*` parameters restore the durable widget values. They go back under `keep.*`, NOT under
    # the widget's own key: the widget key is seeded from `keep.*` at render time, and writing it
    # here -- before Streamlit has built the widget -- would be seeding a key whose widget may never
    # appear on this run.
    for param, raw in params.items():
        name = str(param)
        if name.startswith(_LIST_PREFIX):
            value = _single(raw)
            if value in _EMPTY:
                continue
            keep_key = f"{_KEEP_PREFIX}{name[len(_LIST_PREFIX):]}"
            if keep_key not in state:
                text = str(value)
                state[keep_key] = [] if text == _EMPTY_LIST else text.split(_LIST_SEP)
            continue
        if not name.startswith("w."):
            continue
        value = _single(raw)
        if value in _EMPTY:
            continue
        keep_key = f"{_KEEP_PREFIX}{name[2:]}"
        if state.get(keep_key) in _EMPTY:
            state[keep_key] = _coerce_kept(str(value))


def snapshot(state: Mapping[str, Any]) -> dict[str, str]:
    """The query parameters that represent *state*'s durable values.

    Includes the ``keep.*`` widget values as ``w.*`` parameters. Session state -- and every
    ``keep.*`` entry in it -- is discarded by the browser on refresh, so persisting widget values
    across a section change without also putting them in the URL fixes half the problem and leaves
    F5 exactly as broken as it was.

    Only scalars, and only short ones: a URL has a practical length limit, and these are search
    boxes, sort keys and checkboxes, not caches.
    """
    out: dict[str, str] = {}
    for key, param in PERSISTED.items():
        value = state.get(key.value)
        if value not in _EMPTY and isinstance(value, str | int | float | bool):
            out[param] = str(value)

    for name, value in state.items():
        if not str(name).startswith(_KEEP_PREFIX):
            continue
        short = str(name)[len(_KEEP_PREFIX) :]

        # A multiselect's value. Joined rather than skipped: leaving lists out meant a selection
        # survived a section change (session state kept it) and vanished on F5 -- half-fixed, which
        # is indistinguishable from broken to the person pressing the key.
        if isinstance(value, list | tuple):
            if not all(isinstance(item, str | int | float | bool) for item in value):
                continue
            text = _LIST_SEP.join(str(item) for item in value) if value else _EMPTY_LIST
            if len(text) <= _MAX_KEPT_CHARS:
                out[f"{_LIST_PREFIX}{short}"] = text
            continue

        if value in _EMPTY or not isinstance(value, str | int | float | bool):
            continue
        text = str(value)
        if len(text) <= _MAX_KEPT_CHARS:
            out[f"w.{short}"] = text
    return out


def restore_theme(params: Mapping[str, Any], default: str) -> str:
    """The theme name from the URL, or *default*.

    Validated against the known palettes by the caller; an unknown name there falls back rather than
    raising, so a hand-edited URL cannot break the page.
    """
    value = _single(params.get(THEME_PARAM))
    return str(value) if value not in _EMPTY else default


def _single(value: Any) -> Any:
    """Query parameters may arrive as a list. Take the first, which is what a browser sends."""
    if isinstance(value, list | tuple):
        return value[0] if value else None
    return value


# --------------------------------------------------------------------------------------------------
# The Streamlit-facing helpers. Split out so everything above is testable with plain dicts.
# --------------------------------------------------------------------------------------------------


def load_into_session() -> None:
    """Seed ``st.session_state`` from the URL. Call once, before anything reads state."""
    import streamlit as st

    # `SessionStateProxy` is mapping-like but is not declared as a MutableMapping, so the cast
    # is where that equivalence is asserted rather than assumed.
    restore(cast("MutableMapping[str, Any]", st.session_state), dict(st.query_params))


def sync_to_url() -> None:
    """Write the durable slice of session state back to the URL.

    Only writes when something actually changed. Streamlit re-runs the script on every interaction,
    and assigning to ``st.query_params`` unconditionally would rewrite history on every keystroke.
    """
    import streamlit as st

    desired = snapshot(cast("Mapping[str, Any]", st.session_state))
    # No theme parameter. The console is always dark, so a `theme=` in the address bar promised a
    # choice that no longer exists and would have restored a setting nothing reads.

    current = {k: _single(v) for k, v in dict(st.query_params).items()}
    if current != desired:
        st.query_params.clear()
        for key, value in desired.items():
            st.query_params[key] = value


# ==================================================================================================
# Durable widget values
# ==================================================================================================
#
# THE DEFECT THESE EXIST FOR
#     Streamlit discards a widget's state when the widget is not rendered on a run. Navigating from
#     Scan History to Reports destroys every Scan History widget, so coming back gives an empty
#     search box, a reset sort order and cleared filters -- reported repeatedly as "the state
#     disappears when I change section".
#
#     Mirroring the PAGE into the URL, which is what this module did before, does not touch that:
#     the page was restored and everything on it was not.
#
# THE MECHANISM
#     A widget's key is not where its value lives. The value lives under a separate, durable key
#     that Streamlit never garbage-collects, because no widget is bound to it. The widget is SEEDED
#     from the durable key each run and writes back to it after.
#
#     Two keys instead of one is the whole trick, and it is the same shape as the theme-toggle fix:
#     a widget key belongs to Streamlit's lifecycle, and anything that must outlive that lifecycle
#     needs a key of its own.


def remembered(key: str, default: Any = "") -> Any:
    """The durable value behind a widget, or *default*."""
    import streamlit as st

    return st.session_state.get(f"keep.{key}", default)


def remember_widget(key: str, value: Any) -> None:
    """Record a widget's current value under its durable key."""
    import streamlit as st

    st.session_state[f"keep.{key}"] = value


def _seed(key: str, value: Any) -> None:
    """Put *value* into the widget's own key BEFORE the widget is built.

    ``value=`` / ``index=`` are NOT enough, and that is the whole subtlety here. Streamlit ignores
    those arguments whenever the widget's key already holds state, so a restored value was silently
    discarded on exactly the runs that mattered. Seeding the key itself is the only assignment the
    widget honours -- and it must happen before the widget exists, because Streamlit seals a widget
    key once the widget is drawn. Same rule that governs the theme toggle.
    """
    import streamlit as st

    if key not in st.session_state:
        st.session_state[key] = value


def durable_text(label: str, key: str, *, default: str = "", **kwargs: Any) -> str:
    """A ``st.text_input`` whose contents survive a section change.

    *default* is the first-run text, used only while nothing has been remembered. It exists because
    a box that a plain widget pre-filled (``value=``) renders EMPTY once it becomes durable -- the
    seed is what the widget shows, and seeding it with "" is seeding it blank. That turned Scan
    Center's pre-filled scan name into an empty field.
    """
    import streamlit as st

    _seed(key, str(remembered(key, default)))
    value = st.text_input(label, key=key, **kwargs)
    remember_widget(key, value)
    return str(value or "")


def durable_select(
    label: str, options: Sequence[Any], key: str, *, default: Any = None, **kwargs: Any
) -> Any:
    """A ``st.selectbox`` whose choice survives a section change.

    *default* is the first-run choice, used only while nothing has been remembered -- it is how a
    configured default (the default target, say) gets a say without overriding the operator on every
    subsequent run.

    Falls back to the first option when the remembered choice is no longer available -- an option
    list can change between runs, and a stale value would raise rather than degrade.
    """
    import streamlit as st

    choices = list(options)
    if not choices:
        return None
    previous = remembered(key, None)
    if previous is None and default in choices:
        previous = default
    _seed(key, previous if previous in choices else choices[0])
    # A remembered value can also go stale WHILE the key already exists -- the option list changes
    # between runs. Streamlit raises on a value that is not in `options`, so correct it here.
    if st.session_state.get(key) not in choices:
        st.session_state[key] = choices[0]
    value = st.selectbox(label, choices, key=key, **kwargs)
    remember_widget(key, value)
    return value


def durable_check(label: str, key: str, *, default: bool = False, **kwargs: Any) -> bool:
    """A ``st.checkbox`` whose state survives a section change."""
    import streamlit as st

    _seed(key, bool(remembered(key, default)))
    value = st.checkbox(label, key=key, **kwargs)
    remember_widget(key, value)
    return bool(value)


def durable_multi(
    label: str, options: Sequence[Any], key: str, *, default: Sequence[Any] | None = None, **kwargs: Any
) -> list[Any]:
    """A ``st.multiselect`` whose selection survives a section change and a refresh.

    *default* applies only on the first run, exactly as Streamlit's own does. Afterwards the
    remembered selection wins -- including an EMPTY one, which is why the remembered value is
    checked with ``is None`` rather than for truthiness: an operator who deselected everything meant
    it, and re-applying the default would tick all nine plugins back on behind their back.

    Values that are no longer offered are dropped rather than raising: option lists change between
    runs (a pack is disabled, a category filter narrows the list), and a stale selection restored
    from a bookmark must degrade, not crash.
    """
    import streamlit as st

    choices = list(options)
    fallback = list(default or [])
    previous = remembered(key, None)
    initial = list(previous) if previous is not None else fallback
    _seed(key, [item for item in initial if item in choices])

    current = st.session_state.get(key)
    if isinstance(current, list):
        pruned = [item for item in current if item in choices]
        if pruned != current:
            st.session_state[key] = pruned

    value = list(st.multiselect(label, choices, key=key, **kwargs))

    # Remembered only when it DIFFERS from the default. A selection equal to the default restores
    # identically from "nothing stored", so storing it buys nothing and costs a query parameter in
    # a visible address bar -- with eight facet panels across the console, that was a URL of
    # placeholders describing filters nobody had touched.
    if value == fallback:
        st.session_state.pop(f"{_KEEP_PREFIX}{key}", None)
    else:
        remember_widget(key, value)
    return value


def durable_radio(
    label: str, options: Sequence[Any], key: str, *, default: Any = None, **kwargs: Any
) -> Any:
    """A ``st.radio`` whose choice survives a section change and a refresh.

    *default* is not optional in spirit. Falling through to the first option is fine for a sort
    order and is not fine for a scan profile: the options are alphabetical, so "first" is ``deep``
    -- every payload tier, five attempts each, hours rather than minutes -- and dropping the
    caller's explicit default silently made the most expensive scan in the tool the one that runs
    when somebody presses START without looking.
    """
    import streamlit as st

    choices = list(options)
    if not choices:
        return None
    previous = remembered(key, None)
    if previous is None and default in choices:
        previous = default
    _seed(key, previous if previous in choices else choices[0])
    if st.session_state.get(key) not in choices:
        st.session_state[key] = choices[0]
    value = st.radio(label, choices, key=key, **kwargs)
    remember_widget(key, value)
    return value


def durable_slider(label: str, key: str, *, default: Any, **kwargs: Any) -> Any:
    """A ``st.slider`` whose position survives a section change.

    A range slider's value is a pair of floats, and a pair restored from a URL is a pair of
    STRINGS -- which Streamlit rejects, taking the page down with it. The restored value is
    therefore coerced back to the shape of *default* before it is used, and a value that cannot be
    coerced falls back to the default rather than raising: a hand-edited URL must not be able to
    break the page.
    """
    import streamlit as st

    restored = remembered(key, None)
    _seed(key, default if restored is None else _like(default, restored))
    if not _same_shape(default, st.session_state.get(key)):
        st.session_state[key] = default

    value = st.slider(label, key=key, **kwargs)
    if value == default:
        st.session_state.pop(f"{_KEEP_PREFIX}{key}", None)
    else:
        remember_widget(key, value)
    return value


def _like(default: Any, restored: Any) -> Any:
    """*restored*, converted to the type *default* is -- or *default* when it will not convert."""
    try:
        if isinstance(default, tuple):
            values = restored if isinstance(restored, list | tuple) else [restored]
            if len(values) != len(default):
                return default
            return tuple(type(d)(v) for d, v in zip(default, values, strict=True))
        if isinstance(default, bool):
            return restored in (True, "True", "true", 1, "1")
        if isinstance(default, int | float | str):
            return type(default)(restored)
    except (TypeError, ValueError):
        return default
    return restored


def _same_shape(default: Any, value: Any) -> bool:
    """Whether *value* is usable where *default* is expected."""
    if isinstance(default, tuple):
        return (
            isinstance(value, tuple)
            and len(value) == len(default)
            and all(isinstance(item, int | float) for item in value)
        )
    return isinstance(value, type(default))
