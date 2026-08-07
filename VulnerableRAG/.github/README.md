> ⚠️ **This repository is an intentionally vulnerable application built for security testing.**
> It must never be deployed anywhere reachable. See [`docs/LAB_SAFETY.md`](../docs/LAB_SAFETY.md).

# `.github` — Repository Automation

> **Profile scope:** CI/CD  ·  **SDD reference:** [SDD §35.2](../../RAGStrike/docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Workflows and templates. Phase 1 ships stubs; the lab smoke test arrives with Phase 2.

## Responsibilities

- `workflows/ci.yml` — lint, types, tests.
- `workflows/lab-smoke.yml` — both profiles boot, ingest, and answer.
- `workflows/docker.yml` — image builds.
- Issue and PR templates.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `workflows/ci.yml` | Lint and test | 1 |
| `workflows/lab-smoke.yml` | Both profiles healthy | 2 |

## This folder must NEVER contain

- A workflow that publishes this application to a public registry as `:latest`.
- Secrets in workflow files.
