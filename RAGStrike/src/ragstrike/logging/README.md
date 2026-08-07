# `logging` — Logging Architecture (Layer 3)

> **Layer:** 3 — Infrastructure (cross-cutting)  ·  **SDD reference:** [SDD §30](../../../docs/SDD.md), [ADR-013](../../../docs/annex-c-adrs.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

structlog configuration, context binding, and the **redaction processor**. Redaction is a pipeline stage, not a per-call-site responsibility: one forgotten call site is a leak, and evidence contains, by design, whatever the target disclosed.

Note the package name shadows the standard library's `logging` within this distribution. Absolute imports are mandatory throughout the codebase (enforced by ruff), so `import logging` still resolves to the stdlib; `ragstrike.logging` is always the full path here.

## Responsibilities

- Configure structlog with JSON output and consistent field naming.
- Bind mandatory correlation context to every record: `scan_id`, `case_id`, `probe_id`, `pack_slug`, `attack_id`, `correlation_id`.
- Mask canary tokens, matched secrets, and PII spans **before serialization**.
- Route the four log streams described in `logs/README.md`.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `setup.py` | structlog configuration and stream routing | 1 |
| `processors.py` | Redaction and enrichment processors | 1 |
| `context.py` | Correlation binding helpers | 1 |

## This folder must NEVER contain

- Logging a raw secret, canary, or PII value — the processor exists precisely so this cannot happen by accident.
- f-strings in log calls. Pass structured fields; the message stays constant and greppable.
- Application logic.
