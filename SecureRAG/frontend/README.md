> ⚠️ **This repository is an intentionally vulnerable application built for security testing.**
> It must never be deployed anywhere reachable. See [`docs/LAB_SAFETY.md`](../docs/LAB_SAFETY.md).

# `frontend` — Streamlit User Interface

> **Profile scope:** shared by both profiles  ·  **SDD reference:** [SDD §32.2](../../RAGStrike/docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The chat interface, upload form, and corpus browser. **Identical for both profiles** — same pages, same components, same behaviour. If the two applications ever look different, the differential validation stops measuring security controls and starts measuring incidental UI drift (ADR-009).

The retrieval inspector is not a UI nicety. Displaying retrieved chunks and their sources is what exposes the retrieval internals RAGStrike needs for retrieval-integrity and citation testing, and it is what makes an injection visible to a learner.

## Responsibilities

- Render chat, PDF upload, corpus browser, and retrieval inspector.
- Display retrieved chunks and their claimed sources for every answer.
- Show a prominent profile banner so a user always knows whether they are on the vulnerable or the hardened build.
- Be constructed by a factory parameterized on profile — one codebase, two configurations.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `app_factory.py` | Builds the UI for a given profile | 2 |
| `pages/chat.py` | Chat interface | 2 |
| `pages/upload.py` | PDF upload | 2 |
| `pages/corpus.py` | Corpus browser | 2 |
| `pages/retrieval_inspector.py` | Chunks, scores, and sources per query | 2 |

## This folder must NEVER contain

- Profile-conditional rendering. The UI must not know which profile it is running under, beyond the banner.
- Security controls. Defence belongs in `rag/policy/`, never in the presentation layer.
- Direct vector store or LLM access — the UI talks to `backend/`.
