# `sdk.context` — ScanContext

> **Layer:** cross-cutting (development-time) · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md) · **Guide:** [`docs/sdk-guide.md`](../../../../docs/sdk-guide.md)
> **Status:** implemented — Phase 5.

## Purpose

`ScanContext` — the richer, scan-time companion to Phase 4's `PluginContext`. Carries configuration, logger, target, database (reserved), current plugin, scan id, and framework version, matching the Phase 5 brief's field list exactly.

## Responsibilities

- Define `ScanContext`, built via `ScanContext.from_plugin_context(self.context, target=target)` from inside `execute()`, where `target` is already a parameter.
- Carry a `database` field that is always `None` in the current engine wiring — see the class docstring for why that is correct, not a bug.

## Key exports

| Name | What it is |
|---|---|
| `ScanContext` | Scan-time DI object; see `scan_context.py` for the full rationale. |

## This folder must NEVER contain

- A new parameter on `BaseAttack.execute()` or any other Phase 3/4 signature — that would be an architecture change this phase is not permitted to make. `ScanContext` is assembled by the plugin from information it already has, not injected by a changed contract.
