# `pii-leakage` — PII Leakage Attack Pack

> **OWASP:** LLM02 · **Base impact:** 9/10 · **Impact class:** CONFIDENTIALITY / COMPLIANCE · **Requires:** CHAT · **Phase:** 8
> **Catalogue:** [Annex B](../../../../docs/annex-b-attack-catalog.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Does the application disclose personal data across users, sessions, or authorization boundaries?

Findings carry a `COMPLIANCE` impact class as well, so reports can surface them separately for GDPR/CCPA review. RAGStrike never introduces real personal data into a target; lab PII is synthetic, labelled, and canary-tagged.

## Responsibilities

- **Attacks in this pack:**
- cross-session-recall — asks about a previous user's conversation
- corpus-pii-extraction — enumerates personal data from indexed documents
- aggregation-attack — combines innocuous responses into an identifying profile
- authorization-bypass — requests documents outside the current user's scope
- inference-attack — elicits inferred attributes not stated in the corpus
- **Detector bindings:** Pattern (0.7-1.0), Canary (1.0), Retrieval Integrity (0.8-1.0), LLM Judge (0.6, capped)
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
