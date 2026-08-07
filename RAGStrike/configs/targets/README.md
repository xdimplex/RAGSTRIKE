# `configs/targets` — Target Definitions

> **Layer:** configuration · **SDD:** [`docs/SDD.md`](../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Per-target connection descriptors, capability declarations, and the required authorization block. Only `*.example.yaml` files are committed.

## Responsibilities

- Declare the adapter type and connection details.
- Declare JSONPath request/response mapping for the HTTP adapter — this is what makes a new bespoke API a config change rather than a code change.
- Carry the authorization record: who authorized testing, against what reference.

## Files that will exist here later

- `vulnerable-rag.example.yaml`
- `secure-rag.example.yaml`

## This folder must NEVER contain

- A credential. Reference an environment variable instead.
- A real production endpoint in a committed example.
