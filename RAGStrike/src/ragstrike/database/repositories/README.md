# `database.repositories` — Repository Implementations

> **Layer:** 3 — Infrastructure  ·  **SDD reference:** [SDD §20.2](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Concrete aiosqlite implementations of the repository protocols declared in `core/contracts/repositories.py`. The seam that makes persistence swappable without touching a single line of application logic.

## Responsibilities

- One repository per aggregate: targets, scans, cases, probes, signals, findings, canaries, reports.
- Accept and return domain entities exclusively.
- Keep transactions explicit and scoped.
- Expose only the operations the domain actually needs — a narrow repository is a correctness feature.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `target_repository.py` | Target CRUD plus authorization record | 3 |
| `scan_repository.py` | Scan lifecycle and history queries | 3 |
| `probe_repository.py` | Append and read only — no update, no delete | 3 |
| `finding_repository.py` | Finding persistence and filtered retrieval | 6 |
| `canary_repository.py` | Canary registration and cleanup state | 9 |

## This folder must NEVER contain

- Business rules — a repository stores and retrieves; it does not decide.
- Returning rows or dicts to the application layer.
- An update method on the probe repository.
