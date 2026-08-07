"""``AnalyzerRegistry`` -- analyzers register themselves; the engine never learns their names.

The same principle as the plugin registry, one layer up. Adding an analyzer must not mean editing
the engine, so the engine asks the registry which analyzer claims a category and gets one back
without ever naming a candidate.

**Registration is explicit, not magic.** A decorator or an explicit ``register()`` call, both of
which leave a grep-able trace. Import-scanning would find analyzers nobody meant to ship and make
"which analyzer ran" depend on import order.

**Resolution prefers a specialist, falls back to a generalist.** An analyzer declaring
``handles = ("prompt_injection",)`` wins for that category over one claiming everything. A category
with no specialist still gets analyzed, which is what keeps a brand-new pack working on day one.
"""

from __future__ import annotations

import logging

from ragstrike.analyzers.base.analyzer import BaseAnalyzer

log = logging.getLogger(__name__)


class AnalyzerRegistry:
    """Holds analyzers and resolves one per category."""

    def __init__(self) -> None:
        self._analyzers: dict[str, BaseAnalyzer] = {}

    # -- registration ----------------------------------------------------------------------------

    def register(self, analyzer: BaseAnalyzer, *, replace: bool = False) -> BaseAnalyzer:
        """Add *analyzer* under its ``name``.

        Raises on a duplicate name unless *replace* is set. Silently overwriting would make "which
        analyzer ran" depend on registration order -- and the symptom would be findings that are
        subtly wrong rather than an error anyone notices.
        """
        if not analyzer.name:
            raise ValueError("analyzer must declare a non-empty name")
        if analyzer.name in self._analyzers and not replace:
            raise ValueError(
                f"analyzer {analyzer.name!r} is already registered; "
                "pass replace=True to override deliberately"
            )
        self._analyzers[analyzer.name] = analyzer
        log.debug(
            "analyzer registered",
            extra={"name": analyzer.name, "handles": list(analyzer.handles) or ["*"]},
        )
        return analyzer

    def analyzer(self, cls: type[BaseAnalyzer]) -> type[BaseAnalyzer]:
        """Class decorator: register an instance at import time.

        @registry.analyzer
        class MyAnalyzer(BaseAnalyzer):
            name = "my-analyzer"
            handles = ("prompt_injection",)
        """
        self.register(cls())
        return cls

    def unregister(self, name: str) -> None:
        self._analyzers.pop(name, None)

    def clear(self) -> None:
        """Empty the registry. For tests -- production code registers once at import."""
        self._analyzers.clear()

    # -- lookup ------------------------------------------------------------------------------------

    def get(self, name: str) -> BaseAnalyzer | None:
        return self._analyzers.get(name)

    def all(self) -> list[BaseAnalyzer]:
        """Every registered analyzer, in name order for reproducibility."""
        return [self._analyzers[name] for name in sorted(self._analyzers)]

    def names(self) -> list[str]:
        return sorted(self._analyzers)

    def for_category(self, category: str) -> BaseAnalyzer | None:
        """The analyzer that should handle *category*.

        A specialist -- one naming the category in ``handles`` -- beats a generalist. Among equals,
        name order decides, so resolution is reproducible rather than dependent on registration
        sequence.
        """
        candidates = [a for a in self.all() if a.claims(category)]
        if not candidates:
            return None
        specialists = [a for a in candidates if a.handles]
        return specialists[0] if specialists else candidates[0]

    def __len__(self) -> int:
        return len(self._analyzers)

    def __contains__(self, name: object) -> bool:
        return name in self._analyzers


#: The process-wide registry. A caller wanting isolation constructs its own ``AnalyzerRegistry``
#: rather than mutating this one -- which is what the tests do.
registry = AnalyzerRegistry()


def register(analyzer: BaseAnalyzer, *, replace: bool = False) -> BaseAnalyzer:
    """Register on the default registry."""
    return registry.register(analyzer, replace=replace)


def analyzer(cls: type[BaseAnalyzer]) -> type[BaseAnalyzer]:
    """Decorator registering on the default registry."""
    return registry.analyzer(cls)


__all__: list[str] = ["AnalyzerRegistry", "analyzer", "register", "registry"]
