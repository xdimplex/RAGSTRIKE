"""``FormattingUtils`` -- pure human-readable formatting. No I/O, no state, no randomness."""

from __future__ import annotations

_BYTE_UNITS = ("B", "KB", "MB", "GB", "TB")
_MS_PER_SECOND = 1000
_SECONDS_PER_MINUTE = 60
_BYTES_PER_UNIT = 1024


class FormattingUtils:
    @staticmethod
    def human_duration(milliseconds: int) -> str:
        """``350`` -> ``"350ms"``; ``1500`` -> ``"1.5s"``; ``65000`` -> ``"1m 5s"``."""
        if milliseconds < _MS_PER_SECOND:
            return f"{milliseconds}ms"

        total_seconds = milliseconds / _MS_PER_SECOND
        if total_seconds < _SECONDS_PER_MINUTE:
            return f"{total_seconds:.1f}s"

        minutes, seconds = divmod(int(total_seconds), _SECONDS_PER_MINUTE)
        return f"{minutes}m {seconds}s"

    @staticmethod
    def human_bytes(count: int) -> str:
        """``1536`` -> ``"1.5 KB"``. Binary (1024-based) units, matching how upload limits and
        file sizes are already reported elsewhere in this project (e.g. VulnerableRAG's upload
        size errors)."""
        size = float(count)
        unit = _BYTE_UNITS[0]
        for unit in _BYTE_UNITS:
            if size < _BYTES_PER_UNIT or unit == _BYTE_UNITS[-1]:
                break
            size /= _BYTES_PER_UNIT
        return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"

    @staticmethod
    def percentage(value: float, *, decimals: int = 1) -> str:
        """``0.4567`` -> ``"45.7%"`` at the default precision. Expects a ``0.0-1.0`` fraction,
        matching ``AttackResult.confidence`` and ``ScanSession.coverage``."""
        return f"{value * 100:.{decimals}f}%"


__all__ = ["FormattingUtils"]
