# `backend.schemas` — API Models

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Pydantic request and response models. The contract RAGStrike's HTTP adapter maps onto via JSONPath.

## Responsibilities

- Chat request and response, including retrieved chunks and sources.
- Upload request and response.
- Keep the shape stable — changing it silently breaks every configured target definition.

## Files that will exist here later

- `chat.py`
- `upload.py`
- `sources.py`

## This folder must NEVER contain

- Validation that constitutes a security control. Input validation is a policy (V6).
