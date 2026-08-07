# `core.evidence` — Evidence & Canaries (Layer 2)

> **Layer:** 2 — Application  ·  **SDD reference:** [SDD §16.4](../../../../docs/SDD.md), [ADR-005](../../../../docs/annex-c-adrs.md), [ADR-012](../../../../docs/annex-c-adrs.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Owns the immutable record of what was sent and what came back, and the canary tokens that make leak detection deterministic. Evidence immutability is what makes the offline replay harness possible, and the replay harness is what makes detector development fast.

## Responsibilities

- Mint high-entropy canary tokens and register them against the scan.
- Create immutable `Probe` records for every request/response exchange.
- Track every artifact written into a target and drive cleanup after the scan.
- Mark artifacts `RESIDUAL` when the adapter cannot delete them, so the report can surface them.
- Apply the egress redaction policy (SDD §19.4).

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `recorder.py` | Immutable probe creation | 3 |
| `canary_mint.py` | Token generation and scan registry | 3 |
| `cleanup.py` | Target artifact removal and residual tracking | 9 |
| `redaction.py` | Redaction policy applied on export | 6 |

## This folder must NEVER contain

- Any mutation of a probe after creation.
- Writing an artifact into a target without registering it for cleanup.
- Judging whether an attack succeeded.
