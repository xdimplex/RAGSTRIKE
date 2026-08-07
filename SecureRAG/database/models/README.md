# `database.models` — Table Definitions

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Tables and row shapes for documents, chunks, sessions, and messages.

## Responsibilities

- Declare tables, columns, constraints, and indices.
- Keep chunk provenance columns aligned with `corpus/manifest.yaml`.

## Files that will exist here later

- `tables.py`
- `rows.py`

## This folder must NEVER contain

- Embeddings.
- Business logic.
