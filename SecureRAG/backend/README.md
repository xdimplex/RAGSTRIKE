> ⚠️ **This repository is an intentionally vulnerable application built for security testing.**
> It must never be deployed anywhere reachable. See [`docs/LAB_SAFETY.md`](../docs/LAB_SAFETY.md).

# `backend` — FastAPI Service

> **Profile scope:** shared by both profiles  ·  **SDD reference:** [SDD §32.4](../../RAGStrike/docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The HTTP API RAGStrike actually attacks. It exposes chat, upload, sources, and chunk introspection, and it is the surface the `fastapi` target adapter maps onto.

The API contract is identical across profiles. Only the behaviour behind it differs, because only the policy chain differs.

## Responsibilities

- Expose `/chat`, `/upload`, `/sources`, `/chunks`, `/health`.
- Return retrieved chunks and sources so retrieval integrity is externally testable.
- Be built by an app factory taking a profile, so both applications share one implementation.
- Declare its capabilities at `/health` so adapter capability negotiation has something to negotiate with.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `app_factory.py` | Profile-parameterized FastAPI factory | 2 |
| `routers/chat.py` | Query endpoint | 2 |
| `routers/upload.py` | Document ingestion endpoint | 2 |
| `routers/chunks.py` | Retrieval introspection | 2 |
| `schemas/*.py` | Pydantic request/response models | 2 |

## This folder must NEVER contain

- Security controls implemented inline — every control is a policy in `rag/policy/controls/`, so the diff between profiles stays exactly the control set.
- Authentication that differs between profiles unless it is itself a declared control.
- Any binding to a non-loopback interface by default.
