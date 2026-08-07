# `tests/contract` — Conformance Tests

> **Layer:** verification · **SDD:** [`docs/SDD.md`](../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Runs the SDK conformance suites against every shipped adapter and every first-party pack. This is where Liskov substitutability stops being an aspiration.

## Responsibilities

- Every adapter passes adapter_conformance.
- Every first-party pack passes pack_conformance.
- Run in under a minute; no network.

## Files that will exist here later

- `test_adapter_conformance.py`
- `test_pack_conformance.py`

## This folder must NEVER contain

- Skipping a shipped adapter or pack.
- Network access.
