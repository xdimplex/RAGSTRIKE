# `plugins.base` — Plugin Contracts

> **Layer:** 1 — Ports  ·  **SDD reference:** [SDD §13.2–13.4](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The stable surface third-party pack authors build against, versioned independently of the application as `PLUGIN_API_VERSION` (ADR-015).

## Responsibilities

- Define the pack, attack, detector, mutator, and payload-source contracts.
- Define the manifest, attack, payload, and detector schema versions.
- Provide the compatibility declaration a pack uses to state which API range it supports.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `pack.py` | Pack contract | 4 |
| `attack.py` | Attack definition contract | 4 |
| `detector.py` | Detector contract | 4 |
| `mutator.py` | Variant generation contract | 4 |
| `schemas/` | JSON Schema for every YAML contract | 4 |

## This folder must NEVER contain

- A breaking change without a MAJOR `PLUGIN_API_VERSION` bump — an ecosystem where every core release breaks every pack has no packs.
- Core internals leaking into the public surface.
