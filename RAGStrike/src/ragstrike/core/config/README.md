# `core.config` — Configuration (Layer 2)

> **Layer:** 2 — Application  ·  **SDD reference:** [SDD §21](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Loads, merges, and validates configuration from six precedence levels: built-in defaults → `configs/ragstrike.yaml` → profile → target file → `RAGSTRIKE_*` environment variables → CLI/API overrides. Validation is fail-fast: a scan runs for minutes, so discovering a bad value at minute nine is unacceptable.

## Responsibilities

- Define the typed settings schema (Pydantic — this is a boundary, so Pydantic is correct here).
- Implement the precedence merge exactly as specified in SDD §21.1.
- Validate once at the composition root and fail with the exact field path on error.
- Emit the effective merged configuration snapshot stored on every scan record.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `models.py` | Settings schema: engine, analysis, scoring, plugins, storage, safety, logging | 3 |
| `loader.py` | Layered merge with documented precedence | 3 |
| `validation.py` | Cross-field checks (e.g. remote target requires allowlist entry) | 3 |
| `defaults.py` | Typed built-in defaults | 3 |

## This folder must NEVER contain

- Reading configuration anywhere other than the composition root.
- Silent defaulting of an invalid value — fail, do not guess.
- Secrets in code or in committed YAML.
