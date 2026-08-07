"""Shared presentation helpers.

``format_duration`` lives here because the HTML and Markdown renderers had identical copies of it,
which is how two formats start disagreeing about the same scan: someone fixes the rounding in one
and not the other. Presentation helpers are not computation -- they take a resolved value and choose
how to write it down -- so they belong beside the model rather than inside any one renderer.
"""

from __future__ import annotations

_MS_PER_SECOND = 1000
_SECONDS_PER_MINUTE = 60


def format_duration(milliseconds: int) -> str:
    """``350`` -> ``"350ms"``; ``1500`` -> ``"1.5s"``; ``65000`` -> ``"1m 5s"``."""
    if milliseconds < _MS_PER_SECOND:
        return f"{milliseconds}ms"

    seconds = milliseconds / _MS_PER_SECOND
    if seconds < _SECONDS_PER_MINUTE:
        return f"{seconds:.1f}s"

    minutes, remainder = divmod(int(seconds), _SECONDS_PER_MINUTE)
    return f"{minutes}m {remainder}s"


__all__ = ["format_duration"]
