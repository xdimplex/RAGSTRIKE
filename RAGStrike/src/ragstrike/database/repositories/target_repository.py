"""Target persistence.

Targets are declared in ``configs/targets.yaml``; this table records the ones that have actually
been scanned, so scan history can be joined back to a stable target id even after the YAML changes.

The authorization record is stored alongside, because a scan result that cannot say who authorized
the testing is not much use as evidence.
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
from typing import Any

from ragstrike.database.connection import Database
from ragstrike.models.entities.target import Authorization, Target
from ragstrike.models.values.enums import Capability

log = logging.getLogger(__name__)

_UPSERT = """
INSERT INTO targets (
    id, name, adapter, url, timeout_s, enabled, capabilities, options,
    authorized_by, authorization_ref, authorization_scope, authorized_at, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(name) DO UPDATE SET
    adapter = excluded.adapter,
    url = excluded.url,
    timeout_s = excluded.timeout_s,
    enabled = excluded.enabled,
    capabilities = excluded.capabilities,
    options = excluded.options,
    authorized_by = excluded.authorized_by,
    authorization_ref = excluded.authorization_ref,
    authorization_scope = excluded.authorization_scope,
    authorized_at = excluded.authorized_at
"""


class TargetRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def upsert(self, target: Target) -> Target:
        """Record *target*, returning it with the persisted id.

        Keyed on name rather than id: ``targets.yaml`` mints a fresh id on every load, so keying on
        id would create a new row per run and orphan the scan history from previous ones.
        """
        existing = await self.get_by_name(target.name)
        resolved = target if existing is None else _with_id(target, existing.id)
        auth = resolved.authorization

        async with self.database.connect() as conn:
            await conn.execute(
                _UPSERT,
                (
                    resolved.id,
                    resolved.name,
                    resolved.adapter,
                    resolved.url,
                    resolved.timeout_s,
                    int(resolved.enabled),
                    json.dumps([c.value for c in resolved.capabilities]),
                    json.dumps(resolved.options),
                    auth.authorized_by if auth else "",
                    auth.authorization_ref if auth else "",
                    auth.scope if auth else "",
                    auth.authorized_at.isoformat() if auth else "",
                    resolved.created_at.isoformat(),
                ),
            )
        log.debug("target recorded", extra={"target": resolved.name, "target_id": resolved.id})
        return resolved

    async def get_by_name(self, name: str) -> Target | None:
        async with self.database.connect() as conn:
            cursor = await conn.execute("SELECT * FROM targets WHERE name = ?", (name,))
            row = await cursor.fetchone()
        return _from_row(row) if row else None

    async def list_all(self) -> list[Target]:
        async with self.database.connect() as conn:
            cursor = await conn.execute("SELECT * FROM targets ORDER BY name")
            rows = await cursor.fetchall()
        return [_from_row(row) for row in rows]


def _with_id(target: Target, target_id: str) -> Target:
    return Target(
        id=target_id,
        name=target.name,
        adapter=target.adapter,
        url=target.url,
        timeout_s=target.timeout_s,
        enabled=target.enabled,
        authorization=target.authorization,
        options=target.options,
        capabilities=target.capabilities,
        created_at=target.created_at,
    )


def _from_row(row: Any) -> Target:
    authorization = None
    if row["authorized_by"]:
        authorization = Authorization(
            authorized_by=row["authorized_by"],
            authorization_ref=row["authorization_ref"],
            scope=row["authorization_scope"],
            authorized_at=datetime.fromisoformat(row["authorized_at"]),
        )
    return Target(
        id=row["id"],
        name=row["name"],
        adapter=row["adapter"],
        url=row["url"],
        timeout_s=row["timeout_s"],
        enabled=bool(row["enabled"]),
        authorization=authorization,
        options=json.loads(row["options"] or "{}"),
        capabilities=tuple(Capability(c) for c in json.loads(row["capabilities"] or "[]")),
        created_at=datetime.fromisoformat(row["created_at"]),
    )
