# `rag.session` — Session Memory

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Conversation history. Unbounded by default — weakness V8. Bounding it is a control, not a core behaviour.

## Responsibilities

- Store and replay conversation turns.
- Support explicit reset, which RAGStrike's fresh-session semantics depend on.

## Files that will exist here later

- `memory.py`

## This folder must NEVER contain

- A history cap or periodic re-grounding. Both are controls in `policy/controls/`.
