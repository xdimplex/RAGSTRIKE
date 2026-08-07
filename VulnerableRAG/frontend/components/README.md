# `frontend.components` — UI Components

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Shared widgets: chunk viewer, source list, message bubbles, the profile banner.

## Responsibilities

- Render retrieved chunks with their similarity scores and provenance.
- Render sources exactly as the API reported them — including fabricated ones, which is weakness V9 made visible rather than hidden.

## Files that will exist here later

- `chunk_viewer.py`
- `source_list.py`
- `profile_banner.py`

## This folder must NEVER contain

- Filtering or sanitizing what it displays. The UI shows what the backend returned; hiding a weakness in the presentation layer would make it invisible to a learner.
