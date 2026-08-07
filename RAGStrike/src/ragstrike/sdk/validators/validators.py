"""Reusable, attack-agnostic validation helpers.

Two styles, for two situations:

* ``is_*`` / ``has_*`` -- boolean predicates. Use these in an ``if``; they never raise.
* ``require_*`` -- the same check, but raises :class:`~ragstrike.sdk.exceptions.ValidationError`
  with a message naming exactly what failed. Use these when a malformed response should stop
  ``analyze()`` from proceeding rather than be silently treated as evidence of nothing.

**Nothing here knows what an attack is.** These check that a response exists, that a status code
is in range, that JSON parses, that expected fields are present -- the same handful of questions
every plugin needs answered before it can even start deciding whether an attack worked. Deciding
whether a specific payload *succeeded* is the plugin's own job, in its own ``analyze()``.
"""

from __future__ import annotations

import json
from typing import Any

from ragstrike.core.contracts.target_adapter import TargetResponse
from ragstrike.sdk.exceptions import ValidationError

#: What counts as a "successful" HTTP status by default. Callers needing a different range (e.g.
#: accepting 3xx redirects) pass their own via the ``ok_range`` parameter.
_DEFAULT_OK_RANGE = range(200, 300)


# -- response ----------------------------------------------------------------------------------


def response_exists(response: TargetResponse | None) -> bool:
    return response is not None


def require_response(response: TargetResponse | None) -> TargetResponse:
    """Raises :class:`ValidationError` if *response* is ``None``."""
    if response is None:
        raise ValidationError("Expected a response, got None.")
    return response


def response_has_text(response: TargetResponse) -> bool:
    """Whether the response carries any non-whitespace answer text."""
    return bool(response.text and response.text.strip())


def require_response_text(response: TargetResponse) -> str:
    if not response_has_text(response):
        raise ValidationError("Response has no text.", hint="Check response.error for why.")
    return response.text


# -- status codes --------------------------------------------------------------------------------


def is_valid_status_code(code: int | None, *, ok_range: range = _DEFAULT_OK_RANGE) -> bool:
    """Whether *code* falls in *ok_range*. ``None`` is always invalid -- there is nothing to
    range-check."""
    return code is not None and code in ok_range


def require_valid_status_code(code: int | None, *, ok_range: range = _DEFAULT_OK_RANGE) -> int:
    if not is_valid_status_code(code, ok_range=ok_range):
        raise ValidationError(
            f"Status code {code!r} is not in the expected range "
            f"{ok_range.start}-{ok_range.stop - 1}."
        )
    return code  # type: ignore[return-value]  # narrowed by is_valid_status_code above


# -- JSON -------------------------------------------------------------------------------------


def is_valid_json(text: str) -> bool:
    try:
        json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return False
    return True


def require_valid_json(text: str) -> Any:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValidationError(f"Not valid JSON: {exc}") from exc


# -- fields and metadata --------------------------------------------------------------------------


def fields_exist(data: dict[str, Any], *fields: str) -> bool:
    """Whether every name in *fields* is a key in *data*. Presence only -- a field set to
    ``None`` still counts as existing; pair with your own ``is not None`` check if that
    distinction matters to the caller."""
    return all(field in data for field in fields)


def missing_fields(data: dict[str, Any], *fields: str) -> list[str]:
    """Which of *fields* are absent from *data*, in the order given. Empty list if none are
    missing."""
    return [field for field in fields if field not in data]


def require_fields(data: dict[str, Any], *fields: str) -> dict[str, Any]:
    """Raises :class:`ValidationError` naming every absent field, not just the first."""
    absent = missing_fields(data, *fields)
    if absent:
        raise ValidationError(f"Missing required field(s): {', '.join(absent)}.")
    return data


def has_required_metadata(config: dict[str, Any], *keys: str) -> bool:
    """Whether a plugin's ``context.config`` declares every name in *keys*.

    Intended for use inside a plugin's own ``validate()``, to check that required options were
    supplied in ``metadata.yaml``/``plugins.yaml`` before the plugin is allowed to run.
    """
    return fields_exist(config, *keys)


def require_metadata(config: dict[str, Any], *keys: str) -> dict[str, Any]:
    absent = missing_fields(config, *keys)
    if absent:
        raise ValidationError(
            f"Missing required configuration key(s): {', '.join(absent)}.",
            hint="Set them in the plugin's metadata.yaml options, or in configs/plugins.yaml.",
        )
    return config


__all__ = [
    "fields_exist",
    "has_required_metadata",
    "is_valid_json",
    "is_valid_status_code",
    "missing_fields",
    "require_fields",
    "require_metadata",
    "require_response",
    "require_response_text",
    "require_valid_json",
    "require_valid_status_code",
    "response_exists",
    "response_has_text",
]
