# `packs` — Local Attack Pack Drop-in

> **Layer:** plugin discovery  ·  **SDD reference:** [SDD §13.5](../docs/SDD.md), [ADR-002](../docs/annex-c-adrs.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Drop an attack pack directory in here and RAGStrike discovers it on next start — no pip install, no core edits, no registration step anywhere. This is the second of the two discovery mechanisms (the first being entry points), and it exists so that developing a pack does not require packaging it first.

## Responsibilities

- Hold locally-developed or private packs during development.
- Be scanned at startup according to `plugins.local_pack_dirs` in configuration.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `<pack-name>/pack.yaml` | A pack manifest plus its attacks, payloads, and detectors | 4 |

## This folder must NEVER contain

- First-party packs — those live in `src/ragstrike/attacks/` and ship inside the distribution.
- Anything committed to git by default; local packs are the developer's own.
