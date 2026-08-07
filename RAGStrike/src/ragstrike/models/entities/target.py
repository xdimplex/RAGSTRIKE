"""The system under test.

A ``Target`` is a connection descriptor plus an authorization record. The authorization is not
decoration: no scan starts without one (ADR-017), and it is carried into every report so a result
always says who authorized the testing that produced it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
import uuid

from ragstrike.models.values.enums import Capability


@dataclass(frozen=True, slots=True)
class Authorization:
    """Who authorized testing this target, and under what reference."""

    authorized_by: str
    authorization_ref: str
    scope: str = ""
    authorized_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorized_by": self.authorized_by,
            "authorization_ref": self.authorization_ref,
            "scope": self.scope,
            "authorized_at": self.authorized_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class Target:
    """A registered system under test."""

    id: str
    name: str
    adapter: str
    url: str
    timeout_s: int = 60
    enabled: bool = True
    authorization: Authorization | None = None
    #: Adapter-specific connection detail (paths, JSONPath mapping, headers).
    options: dict[str, Any] = field(default_factory=dict)
    #: Filled in by ``ragstrike targets verify``; empty until the target has been probed.
    capabilities: tuple[Capability, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex

    @property
    def is_authorized(self) -> bool:
        return self.authorization is not None

    def supports(self, capability: Capability) -> bool:
        """Whether this target declares *capability*.

        A target that has never been verified declares nothing, and the scheduler treats an empty
        capability set as "unknown, attempt anyway" rather than "supports nothing" -- otherwise a
        first scan against a fresh target would skip every case and report full coverage of nothing.
        """
        if not self.capabilities:
            return True
        return capability in self.capabilities

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "adapter": self.adapter,
            "url": self.url,
            "timeout_s": self.timeout_s,
            "enabled": self.enabled,
            "options": self.options,
            "capabilities": [c.value for c in self.capabilities],
            "authorization": self.authorization.to_dict() if self.authorization else None,
            "created_at": self.created_at.isoformat(),
        }
