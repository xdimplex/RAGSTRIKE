# `citation-verification` — Citation Verification Attack Pack

> **OWASP:** LLM09 · **Base impact:** 5/10 · **Impact class:** SAFETY · **Requires:** CHAT + LIST_SOURCES · **Phase:** 10
> **Catalogue:** [Annex B](../../../../docs/annex-b-attack-catalog.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Are cited sources real, retrieved, and actually supporting of the claims made?

**Two-tier verification.** The lexical tier is deterministic and sufficient for `citation-existence` and `citation-retrieval-match` — both are exact set operations. Only `claim-grounding` reaches for the judge.

## Responsibilities

- **Attacks in this pack:**
- citation-existence — every cited source must exist in the corpus manifest
- citation-retrieval-match — every cited source must be in that query's retrieval set
- claim-grounding — claims must be lexically supported by the cited chunk
- citation-under-pressure — does discipline degrade when the user demands sources?
- fabricated-source-acceptance — does the app adopt a user-supplied fake citation?
- **Detector bindings:** Citation Verifier (0.9-1.0), Retrieval Integrity (0.9), Canary (1.0), LLM Judge (0.6, capped)
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
