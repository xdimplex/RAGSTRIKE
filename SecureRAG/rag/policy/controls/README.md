# `rag.policy.controls` — Security Controls ★

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

One module per defence. **The secure profile composes all of them; the vulnerable profile composes none.** This directory is the entire difference between the two applications, and reading it is the fastest way to understand what hardening a RAG system actually requires.

## Responsibilities

- Context sanitizer, Unicode normalizer, instruction neutralizer — counter V1, V2.
- Output filter, secret masker, PII masker — counter V3, V4.
- Input validator — counters V6.
- Retrieval filter — counters V7.
- Session bounder — counters V8.
- Citation grounder — counters V9.
- Each independently testable and independently disableable, so a learner can watch exactly which control stops which attack.

## Files that will exist here later

- `context_sanitizer.py`
- `output_filter.py`
- `secret_masker.py`
- `input_validator.py`
- `retrieval_filter.py`
- `session_bounder.py`
- `citation_grounder.py`

## This folder must NEVER contain

- A control the secure profile does not compose. Dead defences are worse than none — they suggest coverage that does not exist.
- Profile detection. Policies do not know which profile assembled them.
