# `context-injection` — Context Injection Attack Pack

> **OWASP:** LLM01, LLM08 · **Base impact:** 8/10 · **Impact class:** INTEGRITY · **Requires:** CHAT · **Phase:** 9
> **Catalogue:** [Annex B](../../../../docs/annex-b-attack-catalog.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Can a user's message be mistaken for retrieved context or system content? Distinct from prompt injection: the goal is not to give an instruction but to **forge provenance** — to make user text occupy the trusted 'retrieved document' slot.

CWE-345, Insufficient Verification of Data Authenticity, is the precise classification here.

## Responsibilities

- **Attacks in this pack:**
- fake-context-block — user message mimics retrieved-context formatting
- source-spoofing — claims a fabricated authoritative source
- citation-forgery — supplies fake citations the model reproduces
- context-priority-manipulation — asserts injected content supersedes retrieved content
- template-boundary-probe — maps the prompt template's delimiters by differential probing
- **Detector bindings:** Structural (0.8-0.9), Differential (0.8-0.9), Citation Verifier (0.9-1.0)
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
