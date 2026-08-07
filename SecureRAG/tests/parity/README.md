# `tests.parity` — Functional Parity ★

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Asserts both profiles answer a fixed set of **benign** queries equivalently over the same corpus.

This is the tier that would be easiest to skip and the one that matters most. Without it the two applications drift, and once they drift RAGStrike's differential validation silently stops measuring security controls while continuing to look correct.

## Responsibilities

- Same corpus, same queries, both profiles, equivalent answers.
- Same retrieval parameters, same chunk counts, same source attributions on benign input.
- Fail loudly on any divergence — a parity failure is an architecture failure, not a flaky test.

## Files that will exist here later

- `test_functional_parity.py`

## This folder must NEVER contain

- Adversarial queries — divergence on those is the entire point of the exercise.
- Tolerances loose enough to hide real drift.
