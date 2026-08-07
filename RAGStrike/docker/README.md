# `docker` — Container Definitions

> **Layer:** deployment  ·  **SDD reference:** [SDD §35.3](../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Multi-stage images and Compose files for RAGStrike and the lab. Placeholders in Phase 1 — no working build yet.

## Responsibilities

- `Dockerfile.api` / `Dockerfile.dashboard` — multi-stage builder + slim runtime, non-root user.
- `docker-compose.yml` — RAGStrike API and dashboard.
- `docker-compose.lab.yml` — adds Ollama, VulnerableRAG, and SecureRAG for differential testing.
- Bind lab services to `127.0.0.1` only. VulnerableRAG is deliberately insecure and must be hard to expose by accident.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `Dockerfile.api` | API image | 11 |
| `Dockerfile.dashboard` | Dashboard image | 11 |
| `docker-compose.yml` | Core services | 11 |
| `docker-compose.lab.yml` | Full differential lab | 11 |

## This folder must NEVER contain

- Publishing lab ports beyond the host.
- Running as root.
- Baking secrets into an image layer.
