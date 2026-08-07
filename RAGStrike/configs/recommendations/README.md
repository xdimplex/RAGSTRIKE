# `configs/recommendations` — Remediation Catalog

> **Layer:** configuration · **SDD:** [`docs/SDD.md`](../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Peer-reviewed remediation entries, retrieved by the recommendation engine. Never generated at runtime (ADR-019): a security report is a compliance artifact, and advice that differs for every reader of the same finding is not one.

## Responsibilities

- One entry per remediation: id, applies_to, rationale, concrete steps, verification, effort, references, OWASP mapping.
- Improving the catalogue improves every past scan on report regeneration.

## Files that will exist here later

- `catalog.yaml`

## This folder must NEVER contain

- An entry without a `verification` step — every recommendation states how to confirm the fix.
- Vague advice. 'Sanitize input' is not a remediation.
