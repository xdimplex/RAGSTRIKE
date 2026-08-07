# `api.streaming` — Server-Sent Events

> **Layer:** Layer 4 · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The SSE endpoint carrying scan progress. SSE rather than WebSockets because the flow is strictly one-directional (ADR-014).

## Responsibilities

- Subscribe to the event bus and stream events for one scan.
- Emit monotonic sequence numbers so a client can detect gaps and resume.
- Handle disconnect cleanly — a dropped client must not affect the scan.

## Files that will exist here later

- `sse.py`

## This folder must NEVER contain

- Bidirectional protocol handling.
- Holding scan state — the bus is the source.
