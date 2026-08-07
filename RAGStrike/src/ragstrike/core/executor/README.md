# `core.executor` — Execution Engine (Layer 2)

> **Layer:** 2 — Application  ·  **SDD reference:** [SDD §15.2](../../../../docs/SDD.md), [ADR-018](../../../../docs/annex-c-adrs.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Performs the scan. Takes the immutable plan from `scheduler/` and drives each attack case against the target through the `TargetAdapter` port, under bounded concurrency and a non-disableable rate limit. It performs I/O and nothing else — it never interprets a response.

## Responsibilities

- Drive cases with `asyncio.TaskGroup` and a bounded semaphore (default 4).
- Enforce the token-bucket rate limit — this cannot be disabled (ADR-017).
- Apply three timeout tiers: per probe, per case, per scan.
- Retry only transport-level and 5xx/429 failures with exponential backoff and jitter. Never retry a semantically valid response — a refusal is data, not an error.
- Isolate every case: any unexpected exception becomes an `ERRORED` case, never an aborted scan (NFR-06).
- Honour `fresh_session` semantics so a success in one case cannot contaminate the next (R-03).
- Support cooperative cancellation without leaving half-written evidence.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `engine.py` | TaskGroup driver | 3 |
| `rate_limiter.py` | Token bucket — mandatory, no disable path | 3 |
| `retry.py` | Backoff and jitter policy | 3 |
| `isolation.py` | Per-case exception guard | 3 |
| `session.py` | Fresh-session semantics and reset | 3 |
| `cancellation.py` | Cooperative cancellation | 3 |

## This folder must NEVER contain

- Interpreting a response — that is `analyzers/`.
- Deciding what to run — that is `scheduler/`.
- A code path that bypasses the rate limiter.
- Blocking calls on the event loop.
