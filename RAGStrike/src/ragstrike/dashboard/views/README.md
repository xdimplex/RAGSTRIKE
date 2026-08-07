# `dashboard.views` — Streamlit Pages

> **Layer:** Layer 4 · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md) · **Guide:** [`docs/dashboard.md`](../../../../docs/dashboard.md)
> **Status:** implemented in Phase 12.

## Purpose

The nine pages. Every one is a pure API client, and every one exposes exactly one
`render(context: PageContext) -> None`.

Nothing imports these modules directly — they are reached through the route registry in
`navigation/routes.py`, so adding a page is one registry entry plus one module.

| Module | Responsibility |
|---|---|
| `home.py` | Posture overview, recent findings, recent activity, quick actions. |
| `scan_center.py` | The one page that starts work: configure, launch, watch, cancel. |
| `targets.py` | Configured targets, health, authorization records, and their CRUD. |
| `plugins.py` | The installed inventory; enable, disable, reload, validate, metadata. |
| `reports.py` | Generated reports; search, filter, sort, open, export, delete. |
| `scan_history.py` | Every previous scan; detail, replay, report generation, comparison. |
| `settings.py` | Session preferences, and the effective configuration read-only. |
| `system_status.py` | Eight subsystems, host resources, uptime, versions. |
| `about.py` | What the tool claims, what it does not, and what is out of scope. |

## Responsibilities

- Ask services for data, hand it to components, turn a click into a service call.
- Show coverage alongside every grade — a grade without its coverage is misleading (ADR-020).
- Require the authorization confirmation before enabling START SCAN (ADR-017). This is a *second*
  gate; the backend enforces each target's own authorization record independently.

## This folder must NEVER contain

- `from ragstrike.core import ...` — machine-enforced by import-linter.
- Business logic or scoring. A page that decides a verdict is a second opinion about the one thing
  the engine exists to decide.
- A request. Pages call services; services build requests.
- A colour. Pages pass `context.palette` to a component and let it decide.
- A re-implementation of a safety rule. The local-only target policy is enforced in
  `target_adapters.build_adapter`; this folder *shows* it, so there is one implementation rather than
  two that can disagree.
