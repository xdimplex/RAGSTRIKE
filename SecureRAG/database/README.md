> ⚠️ **This repository is an intentionally vulnerable application built for security testing.**
> It must never be deployed anywhere reachable. See [`docs/LAB_SAFETY.md`](../docs/LAB_SAFETY.md).

# `database` — Relational Storage

> **Profile scope:** shared by both profiles  ·  **SDD reference:** [SDD §20.1](../../RAGStrike/docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

aiosqlite storage for documents, chunk metadata, sessions, and conversation history. Each profile gets its own database file so the two labs never share state.

**Embeddings do not live here.** They belong to ChromaDB, in `vectorstore/`. SQLite has no vector index; storing embeddings in it means full scans over float blobs.

## Responsibilities

- Store document records, chunk metadata and provenance, sessions, and message history.
- Provide repositories over those aggregates.
- Run numbered forward-only migrations.
- Keep chunk provenance accurate — RAGStrike's retrieval-integrity pack verifies returned chunks against it.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `connection.py` | aiosqlite connection management | 2 |
| `models/tables.py` | Table definitions | 2 |
| `repositories/*.py` | Document, chunk, session repositories | 2 |
| `migrations/0001_initial.sql` | Initial schema | 2 |

## This folder must NEVER contain

- Embeddings or vectors.
- Real personal data. Lab PII is synthetic and labelled.
- Being committed to git — the `.db` file is gitignored.
