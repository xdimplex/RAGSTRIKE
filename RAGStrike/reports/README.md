# `reports` — Generated Reports

> **Layer:** runtime output (gitignored)  ·  **SDD reference:** [SDD §19](../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Rendered HTML and JSON reports. Gitignored. Reports are redacted by default, but they still describe real weaknesses in a real system and should be handled accordingly.

## Responsibilities

- Hold rendered artifacts, referenced by path and content hash from the `reports` table.
- Remain regenerable — a report can always be re-rendered from stored evidence, which is why a rendering failure never loses findings.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `<scan_id>/report.{html,json}` | Rendered artifacts | 6 |

## This folder must NEVER contain

- Being committed to git.
- Being the only copy of a finding — the database is the source of truth.
