"""Request and response mapping for arbitrary JSON HTTP APIs.

WHY THIS IS A SEPARATE MODULE
    The claim the whole project rests on is that **pointing RAGStrike at a different RAG system is a
    change to ``targets.yaml``, never a change to a plugin**. That claim is only as good as the
    mapping layer, and the mapping layer was previously eight lines of dotted-path lookup living
    inside the adapter.

    Eight lines covered VulnerableRAG. They did not cover an API that nests its prompt
    (``{"input": {"query": ...}}``), one that answers inside a list
    (``{"choices": [{"message": {"content": ...}}]}``), or one that needs anything other than a flat
    string field.

WHY JSONPATH
    ``jsonpath-ng`` has been a declared dependency since Phase 1 -- ``requirements.txt`` says it is
    for "configurable request/response mapping in the HTTP adapter" -- and nothing imported it for
    fifteen phases. Either the dependency was wrong or the adapter was. The dependency was right.

    Dotted paths still work and are still the documented default, because ``answer`` is easier to
    read than ``$.answer`` and covers most targets. A path starting with ``$`` is treated as
    JSONPath; anything else is a dotted path. No configuration flag decides which -- the syntax does.
"""

from __future__ import annotations

from typing import Any

from jsonpath_ng import parse as parse_jsonpath
from jsonpath_ng.exceptions import JSONPathError

from ragstrike.core.errors import ConfigurationError


def extract(body: Any, path: str) -> Any:
    """Resolve *path* against *body*, returning ``None`` when it does not match.

    ``$``-prefixed paths are JSONPath and can index lists, filter, and wildcard. Everything else is
    a dotted path, resolved by plain key lookup.

    Returning ``None`` rather than raising is deliberate: a missing optional field (``sources`` on a
    target that has none) is normal. The *caller* decides which absences matter -- the answer field
    is fatal, the sources field is not.
    """
    if not path:
        return None
    if path.startswith("$"):
        return _extract_jsonpath(body, path)
    return _extract_dotted(body, path)


def _extract_jsonpath(body: Any, path: str) -> Any:
    try:
        expression = parse_jsonpath(path)
    except (JSONPathError, ValueError, AttributeError) as exc:
        raise ConfigurationError(
            f"Invalid JSONPath {path!r}: {exc}",
            hint="Check the mapping paths in the target's options block.",
        ) from exc

    matches = [match.value for match in expression.find(body)]
    if not matches:
        return None
    # A single match is the value; several is the list. A path written to select one field should
    # not have to be unwrapped by the caller, and one written with a wildcard should not silently
    # discard everything after the first hit.
    return matches[0] if len(matches) == 1 else matches


def _extract_dotted(body: Any, path: str) -> Any:
    cursor: Any = body
    for part in path.split("."):
        if isinstance(cursor, list):
            # Numeric segments index a list, so `choices.0.text` works without JSONPath.
            if not part.lstrip("-").isdigit():
                return None
            index = int(part)
            if not -len(cursor) <= index < len(cursor):
                return None
            cursor = cursor[index]
            continue
        if not isinstance(cursor, dict) or part not in cursor:
            return None
        cursor = cursor[part]
    return cursor


def assign(payload: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    """Set *value* at a dotted *path* inside *payload*, creating intermediate objects.

    ``assign({}, "input.query", "hi")`` produces ``{"input": {"query": "hi"}}``.

    This is what lets a target whose API nests its prompt be described in configuration rather than
    in code. JSONPath is deliberately **not** supported for writing: a write path that could filter
    or wildcard has no single well-defined destination, and a request builder that guesses is worse
    than one that refuses.
    """
    if path.startswith("$"):
        raise ConfigurationError(
            f"JSONPath cannot be used to build a request: {path!r}.",
            hint="Request fields use dotted paths, such as 'input.query'.",
        )

    cursor = payload
    parts = path.split(".")
    for part in parts[:-1]:
        nxt = cursor.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cursor[part] = nxt
        cursor = nxt
    cursor[parts[-1]] = value
    return payload


def as_list(value: Any) -> list[Any]:
    """Normalise a mapped value to a list. ``None`` becomes empty, a scalar becomes one element."""
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


__all__ = ["as_list", "assign", "extract"]
