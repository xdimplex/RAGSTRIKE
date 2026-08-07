# `api.middleware` — Middleware

> **Layer:** Layer 4 · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Cross-cutting request concerns: correlation id assignment and request logging.

## Responsibilities

- Assign a correlation id to every request and bind it to the logging context, so a log line can be traced back to the request that produced it.
- Log request and response metadata — never bodies, which may contain evidence.

## Files that will exist here later

- `correlation_id.py`
- `request_logging.py`

## This folder must NEVER contain

- Authentication logic that belongs in a dependency.
- Logging request or response bodies.
