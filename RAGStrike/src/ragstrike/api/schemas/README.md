# `api.schemas` — Request & Response Models

> **Layer:** Layer 4 · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Pydantic models for the HTTP boundary. One of only two places in the codebase where Pydantic is correct (the other is configuration).

## Responsibilities

- Define request and response shapes with validation and examples.
- Convert to and from domain entities explicitly — the domain never crosses the wire unchanged.
- Carry the single error envelope shape.

## Files that will exist here later

- `targets.py`
- `scans.py`
- `findings.py`
- `errors.py`
- `events.py`

## This folder must NEVER contain

- Domain entities re-exported as API models. The two evolve for different reasons.
- Business logic in a validator.
