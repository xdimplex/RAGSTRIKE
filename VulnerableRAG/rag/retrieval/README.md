# `rag.retrieval` — Retrieval

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Embed the query, search, optionally rerank. The `on_context_assembly` hook fires downstream.

## Responsibilities

- Similarity search returning chunks with scores and provenance.
- Return results unfiltered — filtering is a control (V7).

## Files that will exist here later

- `retriever.py`
- `reranker.py`

## This folder must NEVER contain

- ACLs, source allowlists, per-user scoping, or relevance thresholds. All four are controls.
