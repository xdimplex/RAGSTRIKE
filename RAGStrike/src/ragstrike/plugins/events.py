"""Plugin event architecture.

**Architecture only.** Phase 4 defines the event vocabulary, the event object, and the bus
protocol; the engine ships with a no-op bus and no persisted subscribers. Later phases (a
progress dashboard, streaming reports, external metrics) can register a real bus without a change
here.

Why declare it now rather than when it is needed:

* The vocabulary is small and stable, and adding an event later means changing every existing
  subscriber to ignore the new one. Fixing the vocabulary up front avoids that.
* Wiring the (no-op) bus into the engine now means later phases add a subscriber, not a plumbing
  refactor.
* A test can already assert that certain events fire in a given order, which is the actual
  invariant plugins care about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol


class PluginEventType(StrEnum):
    """Every event the framework will emit about a plugin.

    Loaded/Enabled/Disabled/Updated are lifecycle events (registration-time).
    Started/Finished/Failed are execution events (per scan, per plugin).
    """

    LOADED = "plugin.loaded"
    ENABLED = "plugin.enabled"
    DISABLED = "plugin.disabled"
    UPDATED = "plugin.updated"
    STARTED = "plugin.started"
    FINISHED = "plugin.finished"
    FAILED = "plugin.failed"


@dataclass(frozen=True, slots=True)
class PluginEvent:
    """One thing that happened to one plugin.

    The ``payload`` is deliberately typed ``dict[str, Any]``: events cross a subscriber boundary
    and each subscriber cares about different fields. Constraining the payload here would force
    every future subscriber to change every time a new field is useful.
    """

    type: PluginEventType
    plugin_slug: str
    scan_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class EventBus(Protocol):
    """What a subscriber-side implementation offers.

    A ``Protocol`` rather than a class so the engine takes an "anything that can ``publish``"
    without importing the concrete implementation. Same shape as the future SSE-backed bus the
    dashboard will consume.
    """

    def publish(self, event: PluginEvent) -> None: ...


class NoOpBus:
    """The default. Publishes into the void.

    Wired into the engine at the composition root so nothing has to null-check the bus. A test can
    substitute :class:`InMemoryBus` to assert on the event stream.
    """

    def publish(self, event: PluginEvent) -> None:  # noqa: ARG002 - Protocol requires the arg
        return None


class InMemoryBus:
    """Records events in order. For tests and short-lived dashboards.

    Not thread-safe by design: the engine is single-loop and this bus is not meant to survive
    beyond one scan. A distributed implementation would live behind the same protocol.
    """

    def __init__(self) -> None:
        self.events: list[PluginEvent] = []

    def publish(self, event: PluginEvent) -> None:
        self.events.append(event)

    def of_type(self, type_: PluginEventType) -> list[PluginEvent]:
        return [event for event in self.events if event.type is type_]
