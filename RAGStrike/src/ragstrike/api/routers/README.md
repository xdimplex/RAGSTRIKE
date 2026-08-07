# `api.routers` — HTTP Routers

> **Layer:** Layer 4 · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

One router per resource. Routers translate HTTP to a use-case call and back. They contain no business logic — if a router grows a decision, it belongs in the orchestrator.

## Responsibilities

- health, version, targets, packs, profiles, scans, findings, reports, compare, recommendations.
- Validate with Pydantic on the way in, serialize on the way out.
- Return 202 with a resource id for long operations; progress arrives over SSE.

## Files that will exist here later

- `targets.py`
- `scans.py`
- `findings.py`
- `reports.py`
- `packs.py`
- `compare.py`

## This folder must NEVER contain

- Business logic.
- Direct database access.
- A breaking change to /api/v1 — that needs /api/v2.
