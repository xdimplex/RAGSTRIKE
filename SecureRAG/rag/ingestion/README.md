# `rag.ingestion` — Ingestion Pipeline

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

load → extract → chunk → embed → store. The policy hooks `on_ingest` and `on_chunk` fire here, and in the vulnerable profile they do nothing.

## Responsibilities

- Orchestrate the pipeline and invoke policy hooks at the declared points.
- Record chunk provenance accurately — RAGStrike's retrieval-integrity pack verifies against it.
- Preserve extracted text verbatim; sanitizing it is a policy decision, not a pipeline one.

## Files that will exist here later

- `pipeline.py`
- `chunker.py`
- `embedder.py`

## This folder must NEVER contain

- Sanitization. That is a control (V2), and putting it here would make the vulnerable profile impossible to build honestly.
