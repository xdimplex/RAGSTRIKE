# `tests.integration` — Integration Tests

> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The orchestrator driving the full pipeline against SDK test doubles, with a real SQLite file and real plugin loading. Everything is real except the target — which is exactly the boundary that makes these deterministic.

## Responsibilities

- Exercise the full pipeline: plan → execute → analyze → score → report.
- Test repositories against a real database with migrations applied.
- Test plugin discovery and activation, including the refusal paths.
- Test the API surface with a test client.

## Files that will exist here later

- `test_orchestrator_pipeline.py`
- `test_repositories.py`
- `test_api.py`
- `test_plugin_loading.py`

## This folder must NEVER contain

- Network access — the test doubles exist for this.
- A live LLM.
- A shared database file across tests.
