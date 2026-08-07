# `target_adapters.local` — Adapter

> **Layer:** 3 — Infrastructure  ·  **SDD reference:** [SDD §12.3](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

In-process adapter for a plain Python callable. Primary use is testing a RAG system in library mode, and it is the adapter the integration test suite leans on hardest because it needs no network at all.

## Responsibilities

- Wrap any callable matching the expected signature.
- Support capability declaration by inspection or explicit configuration.
- Provide the fastest possible feedback loop for developers testing their own code.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `adapter.py` | Local Python adapter | 3 |

## This folder must NEVER contain

- Executing arbitrary user-supplied source — it wraps a callable the operator already imported.
- Attack or detection logic.
- Being imported directly by `core/`.
