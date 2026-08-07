# `retrieval-integrity` — Retrieval Integrity Attack Pack

> **OWASP:** LLM08 · **Base impact:** 8/10 · **Impact class:** INTEGRITY · **Requires:** CHAT + RETURN_CHUNKS · **Phase:** 10
> **Catalogue:** [Annex B](../../../../docs/annex-b-attack-catalog.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Is the retrieval layer returning the right chunks, from authorized sources, with correct provenance?

Where `RETURN_CHUNKS` is unavailable this pack is skipped and recorded as a coverage gap — an outcome the report states explicitly rather than quietly grading around.

## Responsibilities

- **Attacks in this pack:**
- provenance-verification — every chunk must trace to a manifest-declared source
- unauthorized-source-retrieval — attempts retrieval from out-of-scope sources
- relevance-manipulation — crafted queries forcing adversary-chosen chunks
- chunk-tampering-detection — returned text must match stored source text
- empty-retrieval-behaviour — abstain, or fabricate, when nothing relevant is found?
- threshold-probe — does a minimum-relevance threshold exist at all?
- **Detector bindings:** Retrieval Integrity (0.8-1.0), Canary (1.0), Differential (0.8), Threshold (0.7-0.9)
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
