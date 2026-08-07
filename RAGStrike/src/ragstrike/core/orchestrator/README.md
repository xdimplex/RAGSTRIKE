# `core.orchestrator` — Scan Use Case (Layer 2)

> **Layer:** 2 — Application  ·  **SDD reference:** [SDD §25.1](../../../../docs/SDD.md), [§26.1](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The single entry point for the entire pipeline. `run_scan` sequences registry → capability negotiation → plan → execute → analyze → score → recommend → report, and owns the scan state machine. Both the API and the CLI call this same object; neither reimplements any of it.

## Responsibilities

- Assert the authorization record exists before anything else happens (ADR-017).
- Sequence the pipeline and own scan state transitions.
- Publish lifecycle events.
- Reconcile orphaned scans at startup — a process killed mid-scan leaves a non-terminal state that must be marked `FAILED` with the evidence preserved.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `scan_orchestrator.py` | `run_scan` — the use case | 3 |
| `commands.py` | RunScanCommand, CancelScanCommand | 3 |
| `state_machine.py` | Legal scan transitions | 3 |
| `reconciler.py` | Startup recovery of interrupted scans | 3 |

## This folder must NEVER contain

- Domain logic that belongs in a component — the orchestrator sequences, it does not compute.
- Knowledge of HTTP status codes or CLI exit codes.
- Starting a scan without a persisted authorization record.
