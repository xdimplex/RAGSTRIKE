# `backend.routers` — API Routers

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The endpoints RAGStrike attacks. Identical across both profiles — only the behaviour behind them differs, because only the policy chain differs.

## Responsibilities

- chat — the query endpoint, and the primary attack surface.
- upload — document ingestion, the indirect-injection surface.
- sources and chunks — retrieval introspection, without which retrieval-integrity and citation testing are impossible.
- health — reports capabilities, so adapter negotiation has something to negotiate with.

## Files that will exist here later

- `chat.py`
- `upload.py`
- `sources.py`
- `chunks.py`
- `health.py`

## This folder must NEVER contain

- An inline security control. Every control is a policy in `rag/policy/controls/`.
- A `if profile == ...` branch.
