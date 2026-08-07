> ⚠️ **This repository is an intentionally vulnerable application built for security testing.**
> It must never be deployed anywhere reachable. See [`docs/LAB_SAFETY.md`](../docs/LAB_SAFETY.md).

# `scripts` — Lab Utilities

> **Profile scope:** development  ·  **SDD reference:** [Annex A §A.2](../../RAGStrike/docs/annex-a-directory-structures.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Utilities for operating the lab: seeding the corpus and resetting state between test runs.

## Responsibilities

- `seed_corpus.py` — ingest the benign corpus into both profiles identically.
- `reset_lab.py` — clear uploads, vector collections, and databases so scans start from a known state.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `seed_corpus.py` | Identical corpus ingestion for both profiles | 2 |
| `reset_lab.py` | Return the lab to a known clean state | 2 |

## This folder must NEVER contain

- Runtime dependencies of the applications.
- A destructive operation without an explicit confirmation flag.
