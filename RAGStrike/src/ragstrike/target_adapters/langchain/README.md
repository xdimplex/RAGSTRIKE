# `target_adapters.langchain` — Adapter

> **Layer:** 3 — Infrastructure  ·  **SDD reference:** [SDD §12.3](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

In-process adapter wrapping a LangChain `Runnable` or chain object, for testing a RAG pipeline as a library rather than as a service.

## Responsibilities

- Wrap a chain or runnable behind the `TargetAdapter` port.
- Surface retrieved documents as chunks where the chain exposes them.
- Keep LangChain an optional extra — it must never become a base install dependency.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `adapter.py` | LangChain adapter | 12 |

## This folder must NEVER contain

- A hard import of LangChain at package import time — import lazily inside the adapter.
- Attack or detection logic.
- Being imported directly by `core/`.
