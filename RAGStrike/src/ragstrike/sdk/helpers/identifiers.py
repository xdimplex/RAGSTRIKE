"""ID generation.

Every entity the engine persists mints its own id the same way (``uuid.uuid4().hex``, see e.g.
``models/entities/scan.py``). These helpers give plugin code the identical convention for its own
payload ids, evidence ids, or anything else that needs a unique local identifier -- so an id
generated inside a plugin looks like every other id in the system, not like a foreign format.
"""

from __future__ import annotations

import uuid

#: A uuid4 hex digest is 32 characters; asking for more than that would silently return the same
#: 32 characters every time rather than the longer string a caller's `length` implied.
_MAX_SHORT_ID_LENGTH = 32


def new_uuid() -> str:
    """A full 32-character hex UUID4, no dashes -- matches the engine's own id convention
    exactly (``PluginResult.new_id()``, ``ScanSession.new_id()``, etc.)."""
    return uuid.uuid4().hex


def new_short_id(length: int = 8) -> str:
    """A short id for cases where a full UUID is unnecessarily long, e.g. a human-readable log
    tag. Not guaranteed collision-free at scale -- use :func:`new_uuid` for anything persisted or
    compared across a whole scan."""
    if not 1 <= length <= _MAX_SHORT_ID_LENGTH:
        raise ValueError(f"length must be between 1 and {_MAX_SHORT_ID_LENGTH}, got {length}")
    return uuid.uuid4().hex[:length]


__all__ = ["new_short_id", "new_uuid"]
