> ⚠️ **This repository is an intentionally vulnerable application built for security testing.**
> It must never be deployed anywhere reachable. See [`docs/LAB_SAFETY.md`](../docs/LAB_SAFETY.md).

# `configs` — Configuration

> **Profile scope:** shared, with per-profile overrides  ·  **SDD reference:** [SDD §21](../../RAGStrike/docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Shared YAML configuration: model, chunking, retrieval parameters, storage paths, server binding. Per-profile overrides live in `profiles/*/config.yaml`.

## Responsibilities

- Declare model name, embedding model, chunk size and overlap, top-k, and similarity threshold.
- Declare storage paths and the loopback-only server binding.
- Keep retrieval parameters identical across profiles, so a difference in results is a difference in controls.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `config.yaml` | Shared defaults | 1 |
| `logging.yaml` | Logging configuration | 1 |

## This folder must NEVER contain

- Real credentials.
- A non-loopback default binding.
- A security control toggle. Controls are composed in `profiles/`, never configured.
