"""``BaseAnalyzer`` -- the contract an analyzer implements.

The engine ships one general-purpose analyzer that works for every plugin, because every plugin
already produces the same ``PluginResult`` shape. A specialised analyzer is only needed when a
category demands reasoning the general rules cannot express -- and when that day comes, it
subclasses this and registers itself, with no engine change.

**An analyzer is pure.** No network, no clock beyond the finding's timestamp, no database. Given the
same observation and the same configuration it produces the same finding, which is what lets stored
observations be re-analyzed offline after a rule change rather than re-scanned.
"""

from __future__ import annotations

import abc

from ragstrike.analyzers.base.finding import Finding
from ragstrike.analyzers.base.observation import Observation


class BaseAnalyzer(abc.ABC):
    """Turns one :class:`Observation` into one :class:`Finding`.

    Subclasses set :attr:`name` and implement :meth:`analyze`. :attr:`handles` declares which
    categories the analyzer claims; the default claims everything, which is what makes the shipped
    analyzer a working fallback for a pack nobody anticipated.
    """

    #: Registry key. Must be unique.
    name: str = ""

    #: Categories this analyzer claims. Empty means "any", so an unregistered category still gets
    #: analyzed rather than silently producing no finding.
    handles: tuple[str, ...] = ()

    #: Travels onto every finding it produces, because a finding is only interpretable against the
    #: rules and logic that generated it.
    version: str = "1.0.0"

    def claims(self, category: str) -> bool:
        """Whether this analyzer handles *category*."""
        return not self.handles or category in self.handles

    @abc.abstractmethod
    def analyze(self, observation: Observation) -> Finding:
        """Produce a finding. Must be pure."""


__all__ = ["BaseAnalyzer"]
