# `core.events` — Event Bus (Layer 2)

> **Layer:** 2 — Application  ·  **SDD reference:** [SDD §22.3](../../../../docs/SDD.md), [ADR-014](../../../../docs/annex-c-adrs.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

In-process publish/subscribe carrying scan progress. The API's SSE endpoint is a subscriber; the CLI progress display is another. Neither the executor nor the analyzer knows who is listening.

## Responsibilities

- Define the event vocabulary: `scan.*`, `case.*`, `finding.*`.
- Stamp every event with `scan_id` and a monotonic sequence number for gap detection.
- Throttle high-frequency progress events so a 1200-case deep scan does not flood subscribers.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `bus.py` | Async pub/sub | 3 |
| `types.py` | Event dataclasses | 3 |
| `throttle.py` | Rate-limited progress emission | 3 |

## This folder must NEVER contain

- Persisting state — the bus is transient; durable state belongs in `database/`.
- Being the mechanism by which components communicate results — it carries progress, not data flow.
