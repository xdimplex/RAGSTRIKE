# `configs/scoring` — Scoring Model Weights

> **Layer:** configuration · **SDD:** [`docs/SDD.md`](../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Versioned category weight tables. Every scan records the `scoring_model_version` it used, so a score from six months ago is still interpretable.

## Responsibilities

- Declare per-category weights used in stage 2 of scan aggregation.
- One file per model version; files are immutable once released.

## Files that will exist here later

- `v1_0_0.yaml`

## This folder must NEVER contain

- An edit to a released version. Add a new version and bump instead — otherwise every historical comparison silently changes meaning.
- A weight change without a changelog entry.
