# `tests.unit` — Unit Tests

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Pure functions: chunking, prompt building, and each policy control in isolation.

## Responsibilities

- Test each control independently — a control that cannot be tested alone cannot be trusted in a chain.
- No Chroma, no Ollama, no database.

## Files that will exist here later

- `test_chunker.py`
- `test_prompt_builder.py`
- `test_controls.py`

## This folder must NEVER contain

- Network access.
- Asserting the vulnerable profile is secure.
