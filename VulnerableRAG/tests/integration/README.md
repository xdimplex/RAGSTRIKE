# `tests.integration` — Integration Tests

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The ingestion and query pipelines end to end against a real Chroma instance.

## Responsibilities

- Ingest a document, query it, verify chunks and provenance.
- Use a temporary Chroma directory per test.

## Files that will exist here later

- `test_ingestion.py`
- `test_query_pipeline.py`

## This folder must NEVER contain

- Depending on a live Ollama outside a marked test.
- Shared state between tests.
