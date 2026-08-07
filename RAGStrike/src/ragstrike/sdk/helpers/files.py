"""``FileHelper`` -- reading files without hand-rolling try/except at every call site.

Deliberately narrow: reading text and bytes, and checking existence. Payload loading has its own
dedicated module (:mod:`ragstrike.sdk.payload_loader`) with format-aware parsing; this is for
everything else a plugin might need to read -- a fixture, a wordlist, a static asset shipped in
the plugin's own ``assets/`` directory.
"""

from __future__ import annotations

from pathlib import Path

from ragstrike.sdk.exceptions import SdkError


class FileHelper:
    """Stateless; every method is really a function grouped here for discoverability."""

    @staticmethod
    def exists(path: Path) -> bool:
        return path.is_file()

    @staticmethod
    def read_text(path: Path, *, encoding: str = "utf-8") -> str:
        """Raises :class:`~ragstrike.sdk.exceptions.SdkError` with a clear message rather than
        letting a bare ``OSError``/``UnicodeDecodeError`` surface -- so a plugin catching SDK
        errors catches this too."""
        try:
            return path.read_text(encoding=encoding)
        except OSError as exc:
            raise SdkError(
                f"Could not read {path}: {exc}", hint="Check the path and permissions."
            ) from exc
        except UnicodeDecodeError as exc:
            raise SdkError(
                f"{path} is not valid {encoding}: {exc}",
                hint="Confirm the file's actual encoding.",
            ) from exc

    @staticmethod
    def read_bytes(path: Path) -> bytes:
        try:
            return path.read_bytes()
        except OSError as exc:
            raise SdkError(
                f"Could not read {path}: {exc}", hint="Check the path and permissions."
            ) from exc

    @staticmethod
    def try_read_text(path: Path, *, encoding: str = "utf-8", default: str = "") -> str:
        """Never raises. Returns *default* (``""`` unless overridden) if the file cannot be
        read for any reason. Use when a missing optional file should not interrupt a plugin."""
        try:
            return FileHelper.read_text(path, encoding=encoding)
        except SdkError:
            return default


__all__ = ["FileHelper"]
