# `core.scoring` — Risk Scoring (Layer 2, pure)

> **Layer:** 2 — Application (pure functions)  ·  **SDD reference:** [SDD §17](../../../../docs/SDD.md), [ADR-011](../../../../docs/annex-c-adrs.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Pure arithmetic turning verdicts into numbers. `F = 10 · I · E · C` per finding; then per-category maximum → weighted noisy-OR across categories → bounded density adjustment. Every number a report prints must be reproducible by hand from the report itself.

## Responsibilities

- Compute per-finding risk from impact, measured exploitability (`successes/attempts`), and ensemble confidence.
- Aggregate to a scan-level score using the two-stage model — never a mean, never a flat noisy-OR.
- Map scores to severity bands and posture grades.
- Compute the coverage fraction and apply the partial-coverage qualifier below 60%.
- Version the weight tables under `models/` so historical scans stay interpretable.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `finding_score.py` | F = 10 · I · E · C with clamping | 6 |
| `aggregation.py` | Two-stage scan aggregation | 6 |
| `severity.py` | Band mapping | 6 |
| `grade.py` | A–F posture grade | 6 |
| `coverage.py` | Coverage fraction and qualifier | 6 |
| `models/v1_0_0.py` | Versioned category weight table | 6 |

## This folder must NEVER contain

- I/O of any kind.
- An LLM call — enforced by an import-linter contract, because 'scores are never produced by a model' must be machine-checkable, not merely promised.
- Randomness or wall-clock reads — scoring must be deterministic.
- An unversioned change to any weight, band, or formula.
