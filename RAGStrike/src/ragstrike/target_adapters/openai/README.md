# `target_adapters.openai` — Adapter

> **Layer:** 3 — Infrastructure  ·  **SDD reference:** [SDD §12.3](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Adapter for the OpenAI-compatible `/v1/chat/completions` interface. One adapter covers OpenAI, vLLM, LM Studio, and most gateways, because they converged on the same shape.

## Responsibilities

- Speak the OpenAI chat completions API.
- Handle organization headers, rate-limit headers, and token accounting.
- Record token usage as evidence for the unbounded-consumption pack.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `adapter.py` | OpenAI-compatible adapter | 11 |

## This folder must NEVER contain

- Hardcoding api.openai.com — the base URL is configuration, which is what makes it work for vLLM.
- Attack or detection logic.
- Being imported directly by `core/`.
