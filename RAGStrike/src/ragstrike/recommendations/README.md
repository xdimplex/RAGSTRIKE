# `recommendations` — Recommendation Engine (Layer 2)

> **Layer:** 2 — Application  ·  **SDD reference:** [SDD §18](../../../docs/SDD.md), [ADR-019](../../../docs/annex-c-adrs.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Maps findings to remediation guidance retrieved from a versioned YAML catalog. Guidance is never generated at runtime: a security report is a compliance artifact, and advice that differs for every reader of the same finding is not one.

## Responsibilities

- Load and validate the catalog from `configs/recommendations/`.
- Match findings to entries by attack, category, and evidence traits.
- Deduplicate across findings — one prompt-template fix should appear once, not six times.
- Prioritize by **risk reduced per unit of effort**, not by raw severity.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `catalog.py` | Load and validate catalog YAML | 6 |
| `matcher.py` | Finding → catalog entries | 6 |
| `prioritizer.py` | Effort-weighted ordering | 6 |

## This folder must NEVER contain

- Calling an LLM to write advice.
- Hardcoded remediation text inside detector or attack modules.
- Advice without a `verification` step — every recommendation states how to confirm the fix.
