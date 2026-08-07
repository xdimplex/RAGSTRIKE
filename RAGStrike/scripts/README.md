# `scripts` — Developer Utilities

> **Layer:** tooling  ·  **SDD reference:** [SDD §35](../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Maintenance and bootstrap scripts. Convenience only — nothing here may be required at runtime.

## Responsibilities

- `bootstrap_dev.sh` / `.ps1` — one-command environment setup on POSIX and Windows.
- `validate_manifests.py` — offline schema validation of every pack manifest, also run in CI.
- `regenerate_diagrams.py` — export Mermaid sources to SVG.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `bootstrap_dev.sh / bootstrap_dev.ps1` | Venv, install, pre-commit, migrations | 1 |
| `validate_manifests.py` | Manifest validation | 4 |
| `regenerate_diagrams.py` | Diagram export | 6 |

## This folder must NEVER contain

- Logic the application depends on at runtime.
- POSIX-only scripts with no Windows counterpart — the project supports both (NFR-02).
