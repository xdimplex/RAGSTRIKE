# `plugins` — Plugin Subsystem

> **Layer:** 2 — Application (registry) · 3 — Infrastructure (discovery)  ·  **SDD reference:** [SDD §13](../../../docs/SDD.md), [ADR-002](../../../docs/annex-c-adrs.md), [ADR-003](../../../docs/annex-c-adrs.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The load-bearing abstraction of the framework. Dropping a new attack pack into `packs/` — or `pip install`-ing one — must make it discoverable with **zero edits under `core/`**. That is success criterion SC2, and it is verified by a CI test that installs a fixture pack.

Discovery is manifest-first: `pack.yaml` is parsed *before* any pack code is imported, so compatibility and declared permissions are checked before a third party gets execution.

## Responsibilities

- `base/` — the abstract contracts a pack implements.
- `registry/` — discovery policy, SemVer compatibility resolution, activation, health reporting.
- `loader/` — the mechanics: entry-point enumeration, directory scanning, manifest parsing, lazy module import.
- Isolate failure: a malformed or incompatible pack is recorded with a reason and skipped. It must never prevent startup — a security tool that refuses to run because one optional extension is broken simply will not be run.
- Refuse duplicate slugs by activating the higher version and recording the shadowed one. Silent shadowing would change scan results invisibly.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `base/*.py` | Pack, attack, detector, and mutator contracts | 4 |
| `registry/*.py` | Registry, compatibility resolution, health | 4 |
| `loader/*.py` | Entry-point and directory discovery, manifest parser | 4 |

## This folder must NEVER contain

- Executing pack code before the manifest has been validated.
- A hardcoded list of known packs anywhere — that would defeat the entire subsystem.
- Letting one bad pack abort startup.
- Claiming OS-level sandboxing. v1 states the trust model honestly: installing a pack grants the trust of installing a Python package.
