"""``PluginContext`` -- what the framework gives every plugin.

**Plugins never instantiate the database, the logger, the target adapter, the configuration, the
scheduler, or the engine themselves.** They ask the context for what they need and get it back
already wired. This is the seam that keeps a plugin honest: if it needed a Chroma client, it would
have to declare it as a dependency, and the fact that nothing in this context exposes one is a
design statement.

The context is built once per plugin instance, at load time, and stored on ``self`` by
:class:`~ragstrike.plugins.base.attack.BaseAttack`. Setup/execute/cleanup use ``self.context`` and
never construct one of these themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PluginContext:
    """Everything a plugin is allowed to depend on.

    Attributes:
        plugin_id: Canonical slug of the owning plugin. Bound into the logger so every record from
            the plugin says which plugin produced it.
        source: The plugin's directory on disk. Assets, payloads, and schemas live under here.
        payload_dir: ``source / "payloads"``. Precomputed because most plugins want it.
        config: Runtime configuration merged from ``metadata.yaml`` options and ``plugins.yaml``.
            Only the plugin's own subtree is passed in -- a plugin cannot read another plugin's
            configuration.
        timeout_s: Per-plugin timeout, from ``plugins.yaml``. The scheduler enforces it; the
            plugin only reads it.
        severity_override: Optional override from ``plugins.yaml``. The plugin declares a default
            severity in its metadata; an operator can raise or lower it here without touching code.
        logger: A stdlib logger bound with ``slug=`` context. Plugins should use this rather than
            calling ``logging.getLogger`` themselves, so that discovery-time enrichment survives
            into every record.
    """

    plugin_id: str
    source: Path
    payload_dir: Path
    config: dict[str, Any] = field(default_factory=dict)
    timeout_s: int = 60
    severity_override: str | None = None
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("ragstrike.plugin"))

    @classmethod
    def for_plugin(
        cls,
        *,
        plugin_id: str,
        source: Path,
        config: dict[str, Any] | None = None,
        timeout_s: int = 60,
        severity_override: str | None = None,
    ) -> PluginContext:
        """Build a context for the plugin identified by *plugin_id*.

        A convenience constructor: it precomputes ``payload_dir`` and binds the logger, which are
        the two things every caller would otherwise duplicate.
        """
        base = logging.getLogger(f"ragstrike.plugins.{plugin_id}")
        return cls(
            plugin_id=plugin_id,
            source=source,
            payload_dir=source / "payloads",
            config=dict(config or {}),
            timeout_s=timeout_s,
            severity_override=severity_override,
            logger=base,
        )
