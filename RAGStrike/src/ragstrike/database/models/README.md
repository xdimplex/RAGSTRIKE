# `database.models` — Persistence Models

> **Layer:** 3 — Infrastructure  ·  **SDD reference:** [SDD §20.3](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Table definitions and row shapes — the persistence view of the data.

**This is not the domain model.** `src/ragstrike/models/` holds domain entities with invariants and no persistence knowledge; this package holds table structure with no business rules. Keeping them separate is what lets the schema evolve without dragging the domain along, and `mappers.py` is the single place that knows both.

## Responsibilities

- Declare table names, columns, types, constraints, and indices matching SDD §20.3 exactly.
- Define row dataclasses used by the mappers.
- Document every index and why it exists.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `tables.py` | Table and index definitions | 3 |
| `rows.py` | Row dataclasses | 3 |

## This folder must NEVER contain

- Business logic or invariant enforcement — that is the domain's job.
- Being imported by `core/` or `models/`.
