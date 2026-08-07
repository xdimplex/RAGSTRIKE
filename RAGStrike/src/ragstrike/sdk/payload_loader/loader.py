"""``SdkPayloadLoader`` -- lenient payload loading for plugin authors.

Phase 4 already ships a loader: :class:`ragstrike.plugins.base.payloads.PayloadLoader`, used by
:meth:`~ragstrike.plugins.base.attack.BaseAttack.load_payloads`. It is **strict** -- a malformed
file raises :class:`~ragstrike.core.errors.PluginError` and the plugin's ``payloads()`` call
fails outright. That is the right default for the engine's own loading path: a plugin that ships
a broken payload file has a bug worth surfacing loudly at discovery time.

The Phase 5 brief asks for different behaviour: *"Ignore malformed payloads."* That is a
development-time convenience -- while iterating on a large payload set, one bad entry should not
block testing the other nineteen. ``SdkPayloadLoader`` wraps the Phase 4 loader **file by file**,
catches :class:`~ragstrike.core.errors.PluginError` per file, logs it, and continues. It reuses
:meth:`~ragstrike.plugins.base.payloads.PayloadLoader.parse_file` for the actual parsing -- added
to the Phase 4 loader specifically so this wrapper does not have to reimplement YAML/JSON/TXT
parsing rules or rescan the whole directory to isolate one bad file.

Use :class:`~ragstrike.plugins.base.payloads.PayloadLoader` (via ``self.load_payloads()``) when a
malformed payload file should fail the plugin. Use :class:`SdkPayloadLoader` when it should not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path

from ragstrike.core.errors import PluginError
from ragstrike.plugins.base.attack import Payload
from ragstrike.plugins.base.payloads import PayloadLoader
from ragstrike.sdk.exceptions import PayloadError

log = logging.getLogger(__name__)

#: Kept in sync with ``ragstrike.plugins.base.payloads`` by construction: both read this from the
#: same underlying delegate rather than each declaring their own copy of the set.
_SUPPORTED_SUFFIXES = {".yaml", ".yml", ".json", ".txt"}


@dataclass(frozen=True, slots=True)
class SkippedPayloadFile:
    """A payload file the lenient loader could not parse, and why."""

    path: Path
    reason: str


@dataclass(slots=True)
class LoadResult:
    """What :meth:`SdkPayloadLoader.load` produced.

    Both lists are populated even on a fully successful load (``skipped`` is simply empty) --
    callers should not need to special-case "nothing was skipped."
    """

    payloads: list[Payload] = field(default_factory=list)
    skipped: list[SkippedPayloadFile] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.skipped


class SdkPayloadLoader:
    """Loads every payload file in a directory, skipping ones that fail to parse.

    Same supported formats and the same filename-order guarantee (for reproducibility) as
    :class:`~ragstrike.plugins.base.payloads.PayloadLoader`. The only behavioural difference is
    what happens when one file is malformed: this loader records it and moves on instead of
    raising.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        #: The Phase 4 loader, reused only for its per-file parser -- see the module docstring.
        self._delegate = PayloadLoader(root)

    def load(self) -> LoadResult:
        """Parse every payload file, collecting successes and skips separately.

        Never raises for a malformed *file*. It can still raise :class:`PayloadError` if the
        directory itself is not listable -- a permissions problem, not a content problem.
        """
        if not self.root.exists():
            log.debug("no payload directory", extra={"path": str(self.root)})
            return LoadResult()

        try:
            candidates = sorted(
                p
                for p in self.root.iterdir()
                if p.is_file() and p.suffix.lower() in _SUPPORTED_SUFFIXES
            )
        except OSError as exc:
            raise PayloadError(
                f"Cannot list payload directory {self.root}: {exc}",
                hint="Check directory permissions.",
            ) from exc

        result = LoadResult()
        for path in candidates:
            try:
                result.payloads.extend(self._delegate.parse_file(path))
            except PluginError as exc:
                result.skipped.append(SkippedPayloadFile(path=path, reason=exc.message))
                log.warning(
                    "payload file skipped",
                    extra={"path": str(path), "reason": exc.message},
                )

        return result

    def all(self) -> list[Payload]:
        """Convenience for the common case: just the payloads that parsed successfully.

        Equivalent to ``self.load().payloads``. Use :meth:`load` directly when you want to know
        what was skipped and why -- e.g. to surface it in ``validate()``.
        """
        return self.load().payloads
