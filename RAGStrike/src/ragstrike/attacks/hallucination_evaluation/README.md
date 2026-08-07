# `hallucination-evaluation` — Hallucination Evaluation Attack Pack

> **OWASP:** LLM09 · **Base impact:** 5/10 · **Impact class:** SAFETY · **Requires:** CHAT · **Phase:** 10
> **Catalogue:** [Annex B](../../../../docs/annex-b-attack-catalog.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Does the application fabricate when it should abstain? This measures an **application control** — grounding and abstention — not model quality.

**The nonexistent-entity canary is the key design.** Inventing a high-entropy entity name that provably appears nowhere in the corpus makes any substantive answer about it deterministic proof of fabrication — converting the hardest detector problem in the catalogue into a string check. Where that trick is unavailable, findings are labelled model-assisted.

## Responsibilities

- **Attacks in this pack:**
- unanswerable-probe — questions with no answer in the corpus; correct behaviour is abstention
- false-premise — presupposes a fact the corpus contradicts
- nonexistent-entity — asks about an entity that exists nowhere in the corpus
- overconfidence-probe — is uncertainty expressed where evidence is thin?
- numeric-fabrication — requests figures absent from the corpus
- **Detector bindings:** Canary (1.0 for nonexistent-entity), Refusal-Absence (0.8-0.9), LLM Judge (0.6-0.7, capped)
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
