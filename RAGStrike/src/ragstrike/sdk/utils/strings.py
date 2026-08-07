"""``StringUtils`` -- pure string manipulation. No I/O, no state, no randomness.

See :mod:`ragstrike.sdk.helpers` for why this is a separate package from the stateful helpers.
"""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
_NON_SLUG_CHARS = re.compile(r"[^a-z0-9]+")


class StringUtils:
    @staticmethod
    def truncate(text: str, length: int, *, suffix: str = "…") -> str:
        """Cut *text* to at most *length* characters, ending with *suffix* if it was cut.
        The result (including *suffix*) never exceeds *length* characters."""
        if length <= 0:
            return ""
        if len(text) <= length:
            return text
        if len(suffix) >= length:
            return suffix[:length]
        return text[: length - len(suffix)] + suffix

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Collapse runs of whitespace (including newlines and tabs) to single spaces, and
        strip the ends. Useful before substring matching against text that came out of a chunk
        splitter or a PDF extractor, where line breaks land unpredictably."""
        return _WHITESPACE.sub(" ", text).strip()

    @staticmethod
    def contains_any(text: str, *needles: str, case_sensitive: bool = True) -> bool:
        haystack = text if case_sensitive else text.lower()
        candidates = needles if case_sensitive else tuple(n.lower() for n in needles)
        return any(needle in haystack for needle in candidates)

    @staticmethod
    def contains_all(text: str, *needles: str, case_sensitive: bool = True) -> bool:
        haystack = text if case_sensitive else text.lower()
        candidates = needles if case_sensitive else tuple(n.lower() for n in needles)
        return all(needle in haystack for needle in candidates)

    @staticmethod
    def slugify(text: str) -> str:
        """Lowercase, ASCII-fold, non-alphanumeric runs become a single hyphen, leading/trailing
        hyphens stripped. Useful for turning a plugin display name into a stable evidence key."""
        folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        return _NON_SLUG_CHARS.sub("-", folded.lower()).strip("-")


__all__ = ["StringUtils"]
