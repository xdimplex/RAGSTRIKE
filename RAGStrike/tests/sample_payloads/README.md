# `tests.sample_payloads` — Reference Payloads

> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Reference payload YAML used by schema-validation and rendering tests. Small, deliberate, and including the malformed cases — a validator that has only ever seen valid input is untested.

## Responsibilities

- Valid payload sets covering every schema feature.
- Deliberately malformed sets asserting that validation fails with a *precise* error location.
- Templates exercising the non-evaluating renderer, including inputs that would be an expression injection in a normal templating engine (ADR-016).

## Files that will exist here later

- `valid/*.yaml`
- `invalid/*.yaml`
- `rendering/*.yaml`

## This folder must NEVER contain

- A destructive payload, even as a negative test fixture.
- A payload that reaches a real target.
