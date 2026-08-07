# `core` — Application Nucleus (Layers 1–2)

> **Layer:** 1 — Ports · 2 — Application  ·  **SDD reference:** [SDD §11](../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The port definitions and the application services that orchestrate a scan. `core` may depend on `models`; it may never depend on infrastructure or delivery. Concrete adapters, repositories, and renderers arrive by dependency injection at the composition root (`api/dependencies.py`), never by import.

## Responsibilities

- `contracts/` — abstract ports every outer layer implements.
- `config/` — layered configuration load, merge, and fail-fast validation.
- `executor/` — drive attack cases against a target with bounded concurrency, rate limiting, retries, and cancellation.
- `evidence/` — mint canaries, record immutable probes, enforce cleanup and redaction.
- `events/` — in-process pub/sub feeding the SSE progress stream.
- `scoring/` — the pure, versioned risk arithmetic.
- `orchestrator/` — the single use-case entry point, `run_scan`.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `errors.py` | The `RAGStrikeError` exception taxonomy (SDD §29) | 3 |
| `contracts/*.py` | TargetAdapter, AttackPlugin, Detector, Repository, Renderer, EventBus ports | 3 |
| `config/*.py` | Pydantic settings schema, layered loader, validators | 3 |
| `executor/*.py` | Engine, semaphore, token bucket, retry policy, isolation guard, session handling | 3 |
| `evidence/*.py` | Probe recorder, canary mint, cleanup tracker, redaction policy | 3 |
| `scoring/*.py` | Finding score, two-stage aggregation, severity bands, grade, coverage | 6 |
| `orchestrator/*.py` | Scan orchestrator, commands, state machine, startup reconciler | 3 |

## This folder must NEVER contain

- Imports of `target_adapters`, `database`, `api`, `cli`, or `dashboard`.
- Direct instantiation of a concrete adapter or repository — injection only.
- An LLM call anywhere near `scoring/` (enforced by an import-linter contract).
- Framework-specific types leaking into a signature.
