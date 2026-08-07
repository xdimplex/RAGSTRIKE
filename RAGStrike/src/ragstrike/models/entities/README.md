# `models.entities` — Domain Entities

> **Layer:** Layer 1 · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Objects with identity and a lifecycle. Frozen dataclasses; invariants enforced at construction, so an invalid entity is impossible to build.

## Responsibilities

- Target, Authorization, Scan, AttackPack, AttackDefinition, Payload, AttackCase.
- Probe (immutable), Signal, Finding, Recommendation, Canary, Report.

## Files that will exist here later

- `target.py`
- `scan.py`
- `attack_case.py`
- `probe.py`
- `finding.py`
- `canary.py`
- `report.py`

## This folder must NEVER contain

- Pydantic models — these are frozen dataclasses.
- Persistence or serialization knowledge.
- Mutable state; transitions happen through repositories.
