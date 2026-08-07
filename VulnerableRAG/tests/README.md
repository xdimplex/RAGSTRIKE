> ⚠️ **This repository is an intentionally vulnerable application built for security testing.**
> It must never be deployed anywhere reachable. See [`docs/LAB_SAFETY.md`](../docs/LAB_SAFETY.md).

# `tests` — Test Suite

> **Profile scope:** both profiles  ·  **SDD reference:** [SDD §34](../../RAGStrike/docs/SDD.md), [Annex A §A.2.1](../../RAGStrike/docs/annex-a-directory-structures.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Four tiers. The `parity/` tier is the one that matters most and the one that would be easiest to skip: it asserts that both profiles return substantively equivalent answers to a fixed set of benign queries over the same corpus.

Without that assertion, the two applications can drift, and once they drift, RAGStrike's differential validation silently stops measuring security controls while continuing to look correct. Parity is what makes the whole validation strategy honest.

## Responsibilities

- `unit/` — chunking, prompt building, individual policy controls.
- `integration/` — ingestion and query pipelines against a real Chroma instance.
- `parity/` — functional equivalence of the two profiles on benign queries.
- `fixtures/` — sample documents and recorded model responses.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `parity/test_functional_parity.py` | Both profiles answer benign queries equivalently | 11 |
| `policy/test_controls.py` | Each control blocks what it claims to block | 11 |
| `integration/test_query_pipeline.py` | End-to-end query | 2 |

## This folder must NEVER contain

- A test asserting the vulnerable profile is secure — its weaknesses are the specification, and `docs/vulnerabilities.md` is the reference.
- Real personal data or real credentials in fixtures.
- Network calls to anything outside the lab.
