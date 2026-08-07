# `backend.middleware` — Middleware

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Request logging and correlation. Deliberately minimal — the lab has no redaction pipeline, which is itself one of the things a learner should notice about the vulnerable profile.

## Responsibilities

- Assign a request id and log request metadata.
- CORS for the two UI origins.

## Files that will exist here later

- `logging.py`
- `cors.py`

## This folder must NEVER contain

- Rate limiting or authentication unless it is a declared, documented control.
