# `role-override` — Role Override Attack Pack

> **OWASP:** LLM01 · **Base impact:** 7/10 · **Impact class:** INTEGRITY · **Requires:** CHAT · **Phase:** 7
> **Catalogue:** [Annex B](../../../../docs/annex-b-attack-catalog.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Can the assistant's persona, constraints, or refusal policy be replaced?

This pack tests whether *application constraints* hold — not whether the model will produce harmful content. Payloads demand a benign canary as proof of override. Demonstrating that the constraint layer failed never requires eliciting genuinely harmful output, and it will not.

## Responsibilities

- **Attacks in this pack:**
- persona-replacement — assigns a new unconstrained identity
- hypothetical-framing — 'in a fictional world where…'
- nested-simulation — a system simulating an unconstrained model
- constraint-negation — asserts an authority lifted the constraints
- output-format-coercion — a format in which refusal is structurally impossible
- **Detector bindings:** Structural (0.8-1.0), Canary (1.0), Differential (0.7-0.8)
- Declare required capabilities so the scheduler can gate correctly and record accurate coverage.
- Ship a remediation catalog entry for every attack.
- Pass the conformance suite, and validate in **both** directions: detects on VulnerableRAG, silent on SecureRAG.

## Files that will exist here later

- `pack.yaml — manifest: compatibility range, capabilities, permissions`
- `attacks/*.yaml — one definition per technique, with detector bindings and weights`
- `payloads/*.yaml — payload sets by tier (quick / standard / deep)`
- `detectors/*.yaml — bindings; custom detector modules only where built-ins fall short`
- `recommendations/catalog.yaml — remediation entries owned by this pack`
- `tests/ — conformance and unit tests`

## This folder must NEVER contain

- Executable payloads. Payloads are data, rendered by a non-evaluating engine (ADR-016).
- Destructive payloads. `destructive: false` is required and enforced by the conformance suite.
- Imports of private core internals — packs use `sdk/` and `plugins/base/` only.
- Any special handling in the engine. If this pack were deleted, the engine would still start, still scan, and still report, with a coverage gap recorded.
