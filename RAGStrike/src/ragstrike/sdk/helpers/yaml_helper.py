"""``YamlHelper`` -- YAML that fails safely, mirroring :class:`~ragstrike.sdk.helpers.json_helper.JsonHelper`.

Always uses ``yaml.safe_load``/``yaml.safe_dump`` -- never the unsafe loader. Payload files,
plugin manifests, and every other YAML file this framework reads is untrusted-by-default input;
there is no legitimate reason for a plugin to need arbitrary Python object construction from YAML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ragstrike.sdk.exceptions import SdkError
from ragstrike.sdk.helpers.files import FileHelper


class YamlHelper:
    @staticmethod
    def load(text: str) -> Any | None:
        """``None`` on invalid YAML, rather than raising."""
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError:
            return None

    @staticmethod
    def require_load(text: str) -> Any:
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise SdkError(f"Invalid YAML: {exc}") from exc

    @staticmethod
    def dump(value: Any) -> str:
        return yaml.safe_dump(value, sort_keys=False, default_flow_style=False)

    @staticmethod
    def load_file(path: Path) -> Any:
        return YamlHelper.require_load(FileHelper.read_text(path))

    @staticmethod
    def dump_file(path: Path, value: Any) -> None:
        path.write_text(YamlHelper.dump(value), encoding="utf-8")


__all__ = ["YamlHelper"]
