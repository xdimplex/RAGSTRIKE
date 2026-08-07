# `ragstrike` — Package Root

> **Layer:** all  ·  **SDD reference:** [SDD §11](../../docs/SDD.md), [Annex A](../../docs/annex-a-directory-structures.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The importable Python package. Every subpackage below belongs to exactly one architectural layer, and the dependency rule (SDD §7.2) is enforced here by import-linter contracts in `.importlinter` — dependencies point inward only, and CI fails on violation.

**Layer map for this package:**

| Package | Layer | Depends on |
|---|---|---|
| `models/` | 1 — Domain | stdlib only |
| `core/contracts/` | 1 — Ports | `models/` |
| `core/`, `scheduler/`, `analyzers/`, `recommendations/`, `reporters/`, `plugins/` | 2 — Application | Layer 1 |
| `target_adapters/`, `database/`, `logging/` | 3 — Infrastructure | Layer 1 contracts |
| `api/`, `cli/`, `dashboard/` | 4 — Interface | Layer 2 (dashboard: HTTP only) |
| `utils/` | 0 — Pure helpers | stdlib only |
| `sdk/` | cross-cutting | Layer 1 contracts |

## Responsibilities

- Expose `__version__` and `PLUGIN_API_VERSION` (versioned independently — ADR-015).
- Define the package's public surface; everything else is internal.
- Hold no logic of its own.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `__init__.py` | Version constants and public exports | 1 |
| `__main__.py` | `python -m ragstrike` entry point delegating to the CLI | 3 |
| `py.typed` | PEP 561 marker — this package ships type information | 1 |

## This folder must NEVER contain

- Business logic at package root.
- Import-time side effects — no registry population, no config loading, no I/O on import.
- Cross-layer shortcuts that bypass the dependency rule.
