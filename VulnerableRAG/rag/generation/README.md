# `rag.generation` — Generation

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Assemble the prompt, call the model, post-process. The `on_prompt_build` and `on_response` hooks fire here.

## Responsibilities

- Build the prompt from the active profile's template — weak and undelimited for vulnerable, structured and labelled for secure.
- Call Ollama at temperature 0 so scans are reproducible.
- Return output unmodified; filtering is a control (V3).

## Files that will exist here later

- `prompt_builder.py`
- `llm_client.py`
- `pipeline.py`

## This folder must NEVER contain

- Output filtering, secret masking, or prompt protection. All three are controls.
