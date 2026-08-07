# `api` — HTTP Interface (Layer 4)

> **Layer:** 4 — Interface  ·  **SDD reference:** [SDD §22](../../../docs/SDD.md), [ADR-010](../../../docs/annex-c-adrs.md), [ADR-014](../../../docs/annex-c-adrs.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The FastAPI surface, and the **composition root** where concrete adapters, repositories, and renderers are wired into the application layer. The dashboard reaches the engine only through here, which is what keeps the API provably complete: the reference UI cannot cheat.

## Responsibilities

- Expose the versioned REST surface under `/api/v1` (SDD §22.2).
- Validate every request and response with Pydantic — this is a boundary, so Pydantic belongs here.
- Stream scan progress over SSE with monotonic sequence numbers.
- Translate the exception taxonomy into the single error envelope via one table.
- Wire dependencies in `dependencies.py` — the only module in the codebase that knows every concrete implementation.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `app.py` | FastAPI application factory | 6 |
| `dependencies.py` | Composition root / DI wiring | 6 |
| `errors.py` | Exception → HTTP envelope table | 6 |
| `routers/*.py` | One router per resource | 6 |
| `schemas/*.py` | Pydantic request/response models | 6 |
| `streaming/sse.py` | Server-sent events | 6 |

## This folder must NEVER contain

- Business logic — routers call the orchestrator and translate; they do not decide.
- Direct database access, bypassing repositories.
- A breaking change to `/api/v1` — breaking changes require `/api/v2`.
