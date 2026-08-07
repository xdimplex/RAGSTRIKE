# `frontend.pages` — UI Pages

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Chat, upload, corpus browser, and retrieval inspector. Identical for both profiles.

## Responsibilities

- Render the chat interface with retrieved chunks and sources visible.
- Show a prominent profile banner so a user always knows which build they are on.
- Make injections visible — that is the pedagogical point of exposing retrieval internals.

## Files that will exist here later

- `chat.py`
- `upload.py`
- `corpus.py`
- `retrieval_inspector.py`

## This folder must NEVER contain

- Profile-conditional rendering beyond the banner.
- Any security control — defence belongs in `rag/policy/`.
