# `target_adapters.base` — Adapter

> **Layer:** 3 — Infrastructure  ·  **SDD reference:** [SDD §12.3](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Shared adapter scaffolding: the abstract base, common HTTP session handling, capability declaration helpers, and the error translation table that maps provider failures onto the `TargetError` taxonomy.

## Responsibilities

- Provide the abstract base every adapter extends.
- Centralize retry-classification: which provider errors are transient and which are terminal.
- Host the shared conformance fixtures adapters are tested against.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `base_adapter.py` | Abstract base implementation | 3 |
| `errors.py` | Provider error → TargetError translation | 3 |

## This folder must NEVER contain

- Provider-specific logic — that belongs in the concrete adapter folder.
- Attack or detection logic.
- Being imported directly by `core/`.
