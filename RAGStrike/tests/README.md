# `tests` — Test Suite

> **Layer:** verification  ·  **SDD reference:** [SDD §34](../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Eight tiers, each with a distinct job. The tiers matter because most of them verify that the code does what it was written to do, while exactly one — the differential test — verifies that RAGStrike is *right*.

## Responsibilities

- `unit/` — pure functions, no I/O, under 30 seconds.
- `integration/` — orchestrator against test doubles with a real SQLite file and real plugin loading.
- `contract/` — adapter and pack conformance suites.
- `fixtures/` — shared fixtures and the golden evidence corpus for replay tests.
- `sample_payloads/` — reference payload YAML used by schema and rendering tests.
- `sample_reports/` — golden report outputs; renderer changes must diff cleanly against these.
- Later tiers (`golden/`, `system/`, `property/`, `extensibility/`) arrive with the phases that need them.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `conftest.py` | Shared fixtures | 1 |
| `unit/**` | Mirrors the source tree, one module per source module | 3+ |
| `system/test_differential.py` | The keystone: VulnerableRAG must grade E/F, SecureRAG A/B | 10 |
| `system/test_determinism.py` | Same seed twice → identical findings and score | 10 |
| `extensibility/test_zero_core_edit.py` | Fixture pack discovered with no core changes (SC2) | 4 |

## This folder must NEVER contain

- Network access in unit or integration tiers — that is what the test doubles are for.
- A test that depends on a live LLM outside the `system/` tier.
- Real secrets or real personal data in fixtures. Lab data is synthetic and labelled.
