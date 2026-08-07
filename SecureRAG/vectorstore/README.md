> ⚠️ **This repository is an intentionally vulnerable application built for security testing.**
> It must never be deployed anywhere reachable. See [`docs/LAB_SAFETY.md`](../docs/LAB_SAFETY.md).

# `vectorstore` — ChromaDB Integration

> **Profile scope:** shared by both profiles  ·  **SDD reference:** [SDD §20.1](../../RAGStrike/docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The persistent ChromaDB client and collection management. This is where embeddings live — the one place in either repository that holds vectors.

## Responsibilities

- Manage the persistent Chroma client and per-profile collections.
- Handle embedding generation and upsert.
- Expose similarity search with scores, so relevance thresholds are observable and testable.
- Preserve chunk metadata through storage and retrieval — provenance that is lost at write time cannot be verified at read time.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `client.py` | Persistent Chroma client | 2 |
| `collections.py` | Per-profile collection management | 2 |
| `embeddings.py` | Embedding function configuration | 2 |

## This folder must NEVER contain

- Retrieval *filtering* — filtering is a security control and belongs in `rag/policy/controls/`. This package retrieves; policy decides what is allowed through. Putting the filter here would make the vulnerable profile impossible to build honestly.
- Shared collections between profiles.
