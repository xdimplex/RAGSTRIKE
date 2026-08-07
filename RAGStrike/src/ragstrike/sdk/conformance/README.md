# `sdk.conformance` — Conformance Suites

> **Layer:** cross-cutting · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The batteries every pack and every adapter must pass. The adapter suite is how Liskov substitutability is **enforced** rather than assumed.

## Responsibilities

- pack_conformance — schema validity, deterministic rendering, no undeclared network egress or filesystem writes, payload non-destructiveness, honest capability declarations.
- adapter_conformance — the full TargetAdapter contract, including that reset_session actually resets.
- detector_purity — same input, same output, no hidden state, no clock reads.

## Files that will exist here later

- `pack_conformance.py`
- `adapter_conformance.py`
- `detector_purity.py`

## This folder must NEVER contain

- Tests specific to a first-party pack — these are generic by definition.
- Passing when a contract is violated. A conformance suite that can be satisfied by a broken implementation is worse than none.
