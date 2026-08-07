> ⚠️ **This repository is an intentionally vulnerable application built for security testing.**
> It must never be deployed anywhere reachable. See [`docs/LAB_SAFETY.md`](../docs/LAB_SAFETY.md).

# `docker` — Container Definitions

> **Profile scope:** deployment  ·  **SDD reference:** [SDD §35.3](../../RAGStrike/docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Images and Compose definitions for both profiles plus Ollama. Placeholders in Phase 1.

## Responsibilities

- `Dockerfile.vulnerable` and `Dockerfile.secure` — multi-stage, non-root.
- `docker-compose.yml` — both profiles plus Ollama on one network.
- `ollama-init.sh` — pull the pinned Qwen3 tag.
- **Bind every published port to `127.0.0.1` only.**

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `Dockerfile.vulnerable` | VulnerableRAG image | 2 |
| `Dockerfile.secure` | SecureRAG image | 11 |
| `docker-compose.yml` | Loopback-bound lab stack | 2 |

## This folder must NEVER contain

- A port published on `0.0.0.0`. This application is deliberately insecure; exposing it must require deliberate effort, not a default.
- An unpinned model tag — a silent model change breaks reproducibility.
- Running as root.
