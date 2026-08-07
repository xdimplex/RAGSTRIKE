# `models.states` — State Machines

> **Layer:** Layer 1 · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Scan and case lifecycles, plus their legal-transition tables. The tables are data, so an illegal transition is caught by a lookup rather than by a reviewer noticing.

## Responsibilities

- ScanState and its transitions (SDD §26.1).
- CaseState and its transitions (SDD §26.2).
- Expose the transition validator both the orchestrator and the executor use.

## Files that will exist here later

- `scan_state.py`
- `case_state.py`

## This folder must NEVER contain

- Transition *logic* — that belongs to the orchestrator. This declares what is legal.
- Any I/O.
