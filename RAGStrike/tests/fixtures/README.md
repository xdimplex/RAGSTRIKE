# `tests/fixtures` — Shared Fixtures

> **Layer:** verification · **SDD:** [`docs/SDD.md`](../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Fixtures and the committed golden evidence corpus that the analyzer replay tier runs against.

## Responsibilities

- Sample manifests, payload sets, and target definitions.
- The recorded evidence corpus — real responses, captured once, replayed forever.
- Synthetic secrets and PII for detector testing.

## Files that will exist here later

- `manifests/`
- `evidence_corpus/`
- `targets/`

## This folder must NEVER contain

- Real secrets or real personal data. Everything here is synthetic and labelled.
- Fixtures that require network access to load.
