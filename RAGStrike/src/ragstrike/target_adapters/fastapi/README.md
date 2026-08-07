# `target_adapters.fastapi` — Adapter

> **Layer:** 3 — Infrastructure  ·  **SDD reference:** [SDD §12.3](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The reference adapter: any REST/JSON HTTP API. Request shaping and response extraction are **configuration-driven** via JSONPath expressions declared in the target's YAML, so supporting a new bespoke API is a config change rather than a code change — the Open/Closed Principle applied to integration.

## Responsibilities

- Map `TargetRequest` onto an arbitrary JSON request body via declared JSONPath.
- Extract text, chunks, and sources from an arbitrary JSON response via declared JSONPath.
- Handle auth headers, timeouts, and 429 `Retry-After`.
- Support multipart upload for the `INGEST_DOCUMENT` capability.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `adapter.py` | HTTP adapter | 3 |
| `mapping.py` | JSONPath request/response mapping | 3 |

## This folder must NEVER contain

- A hardcoded request shape — that would defeat the point of a configurable adapter.
- Attack or detection logic.
- Being imported directly by `core/`.
