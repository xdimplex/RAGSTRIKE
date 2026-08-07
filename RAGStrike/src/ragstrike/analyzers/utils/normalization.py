"""Shared helpers for the analyzer engine.

Deliberately small. A utils module that grows becomes the real centre of a subsystem, and then
nothing can be understood without reading it. Anything here has to be needed by two or more engines
and belong to none of them.
"""

from __future__ import annotations

import re
from typing import Any
import unicodedata

_WHITESPACE = re.compile(r"\s+")


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Constrain *value* to a range rather than raising.

    Arithmetic overshooting by a rounding error should not abort an analysis run -- the correct
    response is to bound it and carry on.
    """
    return max(low, min(high, value))


def normalize_text(text: str) -> str:
    """NFKC, whitespace collapsed, stripped, lowercased."""
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", text)).strip().lower()


def coerce_float(value: Any, default: float = 0.0) -> float:
    """Best-effort float, falling back to *default*.

    Evidence crosses a JSON boundary, so a field declared numeric can arrive as a string or as
    ``None``. Failing the whole analysis over one malformed field would lose every other finding in
    the scan.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def truncate(text: str, length: int, *, suffix: str = "…") -> str:
    """Cut *text* to at most *length* characters including *suffix*."""
    if length <= 0:
        return ""
    if len(text) <= length:
        return text
    if len(suffix) >= length:
        return suffix[:length]
    return text[: length - len(suffix)] + suffix


def dedupe(values: list[str]) -> list[str]:
    """Remove duplicates, preserving first-seen order.

    Order is kept rather than sorted because in retrieval the first item is usually the most
    relevant, and sorting discards that for no benefit.
    """
    seen: dict[str, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return list(seen)


__all__ = ["clamp", "coerce_float", "dedupe", "normalize_text", "truncate"]
