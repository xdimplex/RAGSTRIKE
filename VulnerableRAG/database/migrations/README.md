# `database.migrations` — Migrations

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Numbered forward-only SQL migrations, one file per change.

## Responsibilities

- 0001_initial.sql — documents, chunks, sessions, messages.
- Record applied migrations.

## Files that will exist here later

- `runner.py`
- `0001_initial.sql`

## This folder must NEVER contain

- Editing a released migration.
- Down-migrations — an untested rollback path is a trap.
