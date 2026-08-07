> ⚠️ **This repository is an intentionally vulnerable application built for security testing.**
> It must never be deployed anywhere reachable. See [`docs/LAB_SAFETY.md`](../docs/LAB_SAFETY.md).

# `rag` — Retrieval-Augmented Generation Core

> **Profile scope:** shared by both profiles  ·  **SDD reference:** [SDD §32.4](../../RAGStrike/docs/SDD.md), [ADR-009](../../RAGStrike/docs/annex-c-adrs.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The shared RAG implementation: ingestion, retrieval, generation, session memory — and `policy/`, which is the single seam at which the two profiles differ.

Everything in this package is identical for VulnerableRAG and SecureRAG. The vulnerable profile composes an empty policy chain; the secure profile composes a full one. That is the *entire* difference between the two applications, which is the only configuration in which the differential test is scientifically meaningful.

## Responsibilities

- `ingestion/` — load → extract → chunk → embed → store.
- `retrieval/` — embed query → similarity search → optional rerank.
- `generation/` — assemble prompt → call model → post-process.
- `policy/` — the SecurityPolicy protocol, the chain, and the five hook points.
- `session/` — conversation memory (bounding it is a policy, not a core behaviour).

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `ingestion/pipeline.py` | Ingestion pipeline with policy hooks | 2 |
| `retrieval/retriever.py` | Similarity search | 2 |
| `generation/prompt_builder.py` | Consumes the active profile's template | 2 |
| `generation/llm_client.py` | Ollama / Qwen3 client | 2 |
| `policy/chain.py` | Ordered policy composition | 2 |

## This folder must NEVER contain

- A hardcoded security control. Every control is a policy the profile composes in.
- A `if profile == 'secure'` branch anywhere. If one appears, ADR-009 has been violated and the differential test is compromised.
- Knowledge of which profile is running.
