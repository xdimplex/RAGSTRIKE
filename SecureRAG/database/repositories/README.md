# `database.repositories` — Repositories

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Data access for documents, chunks, sessions, and messages.

## Responsibilities

- Return domain objects, never rows.
- Preserve chunk provenance through storage and retrieval — provenance lost at write time cannot be verified at read time.

## Files that will exist here later

- `document_repository.py`
- `chunk_repository.py`
- `session_repository.py`

## This folder must NEVER contain

- Business rules.
- Embeddings — those live in ChromaDB.
