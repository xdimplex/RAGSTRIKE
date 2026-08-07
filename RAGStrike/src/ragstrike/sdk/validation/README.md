# `sdk.validation` — Schema Validation

> **Layer:** cross-cutting · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Offline JSON Schema validation of every YAML contract, with precise error locations. Runs without importing pack code, which is what lets CI validate manifests with no environment.

## Responsibilities

- Schemas for pack manifests, attack definitions, payload sets, detector bindings, and recommendation entries.
- Report the exact file, line, and field on failure — 'invalid manifest' is not an error message.

## Files that will exist here later

- `validators.py`
- `schemas/*.json`

## This folder must NEVER contain

- Requiring a Python import to validate a YAML file.
