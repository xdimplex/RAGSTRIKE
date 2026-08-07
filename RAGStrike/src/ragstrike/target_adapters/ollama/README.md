# `target_adapters.ollama` — Adapter

> **Layer:** 3 — Infrastructure  ·  **SDD reference:** [SDD §12.3](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Direct adapter for the Ollama native API. Used to test a model in isolation, without a retrieval layer — useful for separating 'the model complied' from 'the application let it'.

## Responsibilities

- Speak the Ollama native chat API.
- Declare `CHAT` and `STREAMING`; declare no retrieval capabilities, because there is no retrieval.
- Expose model name and version as target metadata for the report.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `adapter.py` | Ollama adapter | 11 |

## This folder must NEVER contain

- Pretending to have retrieval capabilities it does not have.
- Attack or detection logic.
- Being imported directly by `core/`.
