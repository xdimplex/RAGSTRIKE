"""Small shared helpers. Deliberately minimal -- see normalization.py."""

from ragstrike.analyzers.utils.normalization import (
    clamp,
    coerce_float,
    dedupe,
    normalize_text,
    truncate,
)

__all__ = ["clamp", "coerce_float", "dedupe", "normalize_text", "truncate"]
