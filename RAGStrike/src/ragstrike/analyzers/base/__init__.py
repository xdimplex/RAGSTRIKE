"""``ragstrike.analyzers.base`` -- the types the Analyzer Engine is built from.

* :class:`Observation` -- what goes in. Derived from a plugin's existing ``PluginResult``, which is
  why no plugin needed changing.
* :class:`Finding` -- what comes out. Authored by the analyzer, never by a plugin.
* :class:`BaseAnalyzer` -- the contract an analyzer implements.
* :class:`FindingRepository`, :class:`Analyzer` -- ports something else implements.
"""

from ragstrike.analyzers.base.analyzer import BaseAnalyzer
from ragstrike.analyzers.base.finding import Finding
from ragstrike.analyzers.base.observation import Observation
from ragstrike.analyzers.base.ports import Analyzer, FindingRepository

__all__ = [
    "Analyzer",
    "BaseAnalyzer",
    "Finding",
    "FindingRepository",
    "Observation",
]
