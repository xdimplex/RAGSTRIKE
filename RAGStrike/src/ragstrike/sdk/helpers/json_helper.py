"""``JsonHelper`` -- JSON that fails safely instead of raising ``json.JSONDecodeError`` into
plugin code that was not expecting it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ragstrike.sdk.exceptions import SdkError
from ragstrike.sdk.helpers.files import FileHelper


class JsonHelper:
    @staticmethod
    def loads(text: str) -> Any | None:
        """``None`` on invalid JSON, rather than raising. Use :meth:`require_loads` when
        malformed JSON should stop the caller instead."""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def require_loads(text: str) -> Any:
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError) as exc:
            raise SdkError(f"Invalid JSON: {exc}") from exc

    @staticmethod
    def dumps(value: Any, *, indent: int | None = None) -> str:
        return json.dumps(value, indent=indent, default=str)

    @staticmethod
    def load_file(path: Path) -> Any:
        return JsonHelper.require_loads(FileHelper.read_text(path))

    @staticmethod
    def dump_file(path: Path, value: Any, *, indent: int = 2) -> None:
        path.write_text(JsonHelper.dumps(value, indent=indent), encoding="utf-8")


__all__ = ["JsonHelper"]
