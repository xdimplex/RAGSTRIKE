# `indirect-prompt-injection` — Indirect Prompt Injection Attack Pack

> **OWASP:** LLM01 · **Base impact:** 9/10 · **Impact class:** INTEGRITY · **Requires:** CHAT + INGEST_DOCUMENT · **Phase:** 7
> **Catalogue:** [Annex B](../../../../docs/annex-b-attack-catalog.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Can content in the retrieval corpus give instructions to the model? This is the defining RAG vulnerability: the adversary needs no access to the chat interface at all, only the ability to influence a document the corpus ingests.

Every attack is a two-phase case with `depends_on` ordering: ingest, then query. Every ingested artifact is canary-tagged, tracked, and removed by cleanup; residuals are reported.

## Responsibilities

- **Attacks in this pack:**
- hidden-text-injection — white-on-white, tiny font, off-canvas
- metadata-injection — instruction in PDF metadata the extractor reads
- zero-width-injection — zero-width and bidirectional control characters
- authority-document — a document claiming to supersede the system prompt
- retrieval-bait — engineered to rank highly for common queries, then inject
- cross-document-chain — split across two documents, assembled on retrieval
- **Detector bindings:** Canary (1.0), Retrieval Integrity (0.8-0.9), Differential (0.8)
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
