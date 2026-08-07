# `models.values` — Value Objects

> **Layer:** Layer 1 · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Objects defined entirely by their value: no identity, always immutable, always valid.

## Responsibilities

- Severity, Confidence, RiskScore, PostureGrade, Capability, ImpactClass, CanaryToken.
- Reject invalid values at construction — a Confidence of 1.4 must be unconstructible.

## Files that will exist here later

- `severity.py`
- `confidence.py`
- `risk_score.py`
- `posture_grade.py`
- `capability.py`

## This folder must NEVER contain

- Behaviour beyond validation and conversion.
- Any dependency on an entity.
