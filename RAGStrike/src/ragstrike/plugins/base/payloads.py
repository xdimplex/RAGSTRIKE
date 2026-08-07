"""Payload loading from disk.

Every plugin owns its payloads. **Payloads never live inside the engine.** That is not a stylistic
choice: putting payloads in the engine would mean shipping attack corpora with the framework, and
the framework must remain useful when zero real attacks are installed.

Three formats supported, all of which are ``data``:

* **YAML** -- structured payloads with variables, tiers, and expected outcomes. The canonical
  format.
* **JSON** -- structurally equivalent to YAML; useful for programmatically generated payload sets.
* **TXT** -- one payload per non-empty line, for quick tests and one-shot corpora.

The loader is deliberately non-evaluating: no ``eval``, no ``exec``, no Jinja, no attribute
traversal. If a plugin needs derived payloads, it generates them in Python inside its own
``payloads()`` method -- that is code, subject to the same review the rest of the plugin gets, and
distinct from the data files that live under ``payloads/``.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any

import yaml

from ragstrike.core.errors import PluginError
from ragstrike.plugins.base.attack import Payload

log = logging.getLogger(__name__)

#: Extensions the loader accepts. Anything else in ``payloads/`` is ignored -- so a plugin can drop
#: a README next to its payload files without confusing the loader.
_SUPPORTED = {".yaml", ".yml", ".json", ".txt"}


@dataclass(frozen=True, slots=True)
class PayloadFile:
    """A single file's worth of payloads, with its source path retained for diagnostics."""

    path: Path
    payloads: list[Payload]


class PayloadLoader:
    """Reads payloads from a plugin's ``payloads/`` directory.

    Instantiated by a plugin (or by :class:`~ragstrike.plugins.base.attack.BaseAttack.load_payloads`
    for the common case). Never instantiated by the engine, because the engine does not know that a
    concept called "payload" exists -- it hands the plugin a target and asks what to send.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def all(self) -> list[Payload]:
        """Every payload in this plugin's directory, in filename order.

        Filename order makes payload sequences reproducible across runs, which matters because the
        scoring model treats ``successes / attempts`` as a measurement and a reordered payload
        stream is a different measurement.
        """
        payloads: list[Payload] = []
        for source in self.files():
            payloads.extend(source.payloads)
        return payloads

    def parse_file(self, path: Path) -> list[Payload]:
        """Parse a single payload file, independent of the rest of the directory.

        Added in Phase 5 -- a small, purely additive exposure of the parsing logic ``files()``
        already used internally, with no change to that method's behaviour. It exists because
        ``ragstrike.sdk.payload_loader.SdkPayloadLoader`` needs to parse files one at a time and
        skip individually-malformed ones, and calling ``files()`` for that would rescan the whole
        directory and raise on the *first* malformed file it encounters in sort order -- not
        necessarily the file the caller is asking about. This method has no such side effect: it
        parses exactly the file it is given.
        """
        return self._parse(path)

    def files(self) -> list[PayloadFile]:
        if not self.root.exists():
            log.debug("no payload directory", extra={"path": str(self.root)})
            return []

        collected: list[PayloadFile] = []
        for path in sorted(self.root.iterdir()):
            if not path.is_file() or path.suffix.lower() not in _SUPPORTED:
                continue
            collected.append(PayloadFile(path=path, payloads=self._parse(path)))
        return collected

    # -- internals ---------------------------------------------------------------------------

    def _parse(self, path: Path) -> list[Payload]:
        suffix = path.suffix.lower()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PluginError(
                f"Cannot read payload file {path}: {exc}",
                hint="Check file permissions.",
            ) from exc

        if suffix == ".txt":
            return self._from_lines(path, text)
        if suffix == ".json":
            return self._from_structured(path, self._safe_json(path, text))
        return self._from_structured(path, self._safe_yaml(path, text))

    @staticmethod
    def _safe_json(path: Path, text: str) -> Any:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise PluginError(f"{path}: invalid JSON: {exc}") from exc

    @staticmethod
    def _safe_yaml(path: Path, text: str) -> Any:
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise PluginError(f"{path}: invalid YAML: {exc}") from exc

    def _from_lines(self, path: Path, text: str) -> list[Payload]:
        payloads: list[Payload] = []
        for index, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            payloads.append(
                Payload(
                    id=f"{path.stem}:{index}",
                    content=stripped,
                    tier="standard",
                    description=f"line {index} of {path.name}",
                )
            )
        return payloads

    def _from_structured(self, path: Path, data: Any) -> list[Payload]:
        """Accept two shapes:

        * A top-level list of payload dicts.
        * A mapping with a ``payloads:`` list, mirroring Annex B's payload-set schema.

        Anything else is a configuration error and is refused, because a silent "no payloads found"
        would be indistinguishable from a plugin with an empty file.
        """
        if isinstance(data, dict):
            data = data.get("payloads") or data.get("items") or data.get("data")

        if not isinstance(data, list):
            raise PluginError(
                f"{path}: expected a list of payloads (or a mapping with a 'payloads:' key), "
                f"got {type(data).__name__}."
            )

        payloads: list[Payload] = []
        for index, entry in enumerate(data):
            if isinstance(entry, str):
                payloads.append(Payload(id=f"{path.stem}:{index}", content=entry, tier="standard"))
                continue
            if not isinstance(entry, dict):
                raise PluginError(
                    f"{path}: payload #{index} is not a mapping or string ({type(entry).__name__})."
                )

            content = entry.get("content") or entry.get("template") or entry.get("prompt")
            if not content:
                raise PluginError(
                    f"{path}: payload #{index} has no 'content', 'template', or 'prompt'."
                )
            payloads.append(
                Payload(
                    id=str(entry.get("id", f"{path.stem}:{index}")),
                    content=str(content),
                    tier=str(entry.get("tier", "standard")),
                    expects=dict(entry.get("expects") or {}),
                    description=str(entry.get("description", "")),
                )
            )
        return payloads
