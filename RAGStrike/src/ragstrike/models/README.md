# `models` — Domain Model (Layer 1)

> **Layer:** 1 — Domain  ·  **SDD reference:** [SDD §10](../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The business vocabulary of RAGStrike: entities, value objects, and state enums. This is the innermost layer. It knows nothing about HTTP, SQL, YAML, LLMs, or files, and it imports nothing beyond the standard library and `typing`.

**Do not confuse this with `database/models/`.** This package holds *domain* objects with invariants and behaviour. `database/models/` holds *persistence* row shapes and table definitions. The mapping between them lives in `database/mappers.py`, and it is the only place that knows both.

## Responsibilities

- Define entities: Target, Authorization, Scan, AttackPack, AttackDefinition, Payload, AttackCase, Probe, Signal, Finding, Recommendation, Canary, Report.
- Define value objects: Severity, Confidence, RiskScore, PostureGrade, Capability, ImpactClass, CanaryToken.
- Define state machines and their legal transitions: ScanState, CaseState.
- Enforce invariants at construction — an invalid domain object must be impossible to build.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `entities/*.py` | One frozen dataclass per entity (SDD §10.2) | 3 |
| `values/*.py` | Value objects and enums (SDD §10.3) | 3 |
| `states/scan_state.py` | Scan state enum plus the legal-transition table (SDD §26.1) | 3 |
| `states/case_state.py` | Attack case state enum plus transitions (SDD §26.2) | 3 |

## This folder must NEVER contain

- Any import from `core`, `database`, `api`, `cli`, `dashboard`, or `target_adapters`.
- Pydantic `BaseModel` — domain objects are frozen dataclasses; Pydantic lives at API and config boundaries only.
- Persistence concerns: no table names, no SQL, no serialization format assumptions.
- Mutable entities — mutation happens through repository transitions, not attribute assignment.
