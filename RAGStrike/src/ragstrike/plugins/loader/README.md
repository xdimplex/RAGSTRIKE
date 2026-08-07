# `plugins.loader` — Discovery Mechanics

> **Layer:** 3 — Infrastructure  ·  **SDD reference:** [SDD §13.5](../../../../docs/SDD.md), [ADR-002](../../../../docs/annex-c-adrs.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Finds candidate packs and reads their manifests. Two mechanisms: the `ragstrike.attack_packs` entry-point group for pip-installed packs, and configured local directories for development and private packs.

## Responsibilities

- Enumerate entry points and configured local pack directories.
- Parse `pack.yaml` **without importing pack code** (ADR-003).
- Validate attack, payload, and detector schemas before activation.
- Import declared custom modules lazily, only when a detector is actually needed.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `entry_point_discovery.py` | importlib.metadata entry points | 4 |
| `directory_discovery.py` | Local `packs/` scanning | 4 |
| `manifest_parser.py` | Manifest parsing with no code import | 4 |
| `loader.py` | Lazy module import | 4 |

## This folder must NEVER contain

- Importing a pack module before its manifest is validated — that inverts the safety ordering.
- Deciding compatibility policy — that is `registry/`.
