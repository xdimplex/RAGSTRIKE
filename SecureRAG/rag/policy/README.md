> ⚠️ **This repository is an intentionally vulnerable application built for security testing.**
> It must never be deployed anywhere reachable. See [`docs/LAB_SAFETY.md`](../docs/LAB_SAFETY.md).

# `rag.policy` — The Security Seam ★

> **Profile scope:** the only difference between the two profiles  ·  **SDD reference:** [SDD §33](../../../RAGStrike/docs/SDD.md), [ADR-009](../../../RAGStrike/docs/annex-c-adrs.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The most important package in this repository. `SecurityPolicy` implementations hook into five points in the RAG pipeline; a profile composes a chain of them. VulnerableRAG's chain is empty. SecureRAG's is full.

**Five hook points:** `on_ingest`, `on_chunk`, `on_context_assembly`, `on_prompt_build`, `on_response`.

Because this is the only seam, the diff between `profiles/vulnerable/` and `profiles/secure/` is a working, executable remediation guide — arguably the most valuable teaching artifact either repository produces.

## Responsibilities

- Define the `SecurityPolicy` protocol and the ordered chain.
- `controls/` — one module per defence: context sanitizer, Unicode normalizer, instruction neutralizer, output filter, secret masker, PII masker, input validator, retrieval filter, session bounder, citation grounder.
- Keep each control independently testable and independently disableable, so a learner can watch exactly which control stops which attack.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `protocol.py` | SecurityPolicy interface | 2 |
| `chain.py` | Ordered composition | 2 |
| `hooks.py` | The five hook points | 2 |
| `controls/*.py` | One module per control (SDD §33) | 2 |

## This folder must NEVER contain

- A control that is enabled by configuration rather than by profile composition. A misconfiguration that silently hardens the vulnerable target would invalidate every scan result with no visible symptom.
- A control the secure profile does not compose — dead defences are worse than none, because they suggest coverage that does not exist.
- Profile detection logic. Policies do not know which profile assembled them.
