# `database.migrations` — Schema Migrations

> **Layer:** 3 — Infrastructure  ·  **SDD reference:** [SDD §20.2](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Numbered, checksummed, forward-only SQL migrations. The migration runner verifies checksums at startup and fails fast on mismatch.

## Responsibilities

- `runner.py` — apply pending migrations in order, record them, verify checksums.
- `NNNN_name.sql` — one file per migration, numbered sequentially.
- Record applied migrations in `schema_migrations`.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `runner.py` | Checksum-verified forward-only runner | 3 |
| `0001_initial.sql` | Targets, profiles, scans, cases, probes, signals, findings, reports | 3 |
| `0002_canaries.sql` | Canary tracking and cleanup state | 9 |

## This folder must NEVER contain

- Editing a released migration — the checksum will mismatch and startup will fail, correctly. Write a new migration instead.
- Down-migrations. Forward-only is deliberate: a rollback path that is never tested is a trap.
- Data-destructive operations without an explicit, documented, reviewed decision.
