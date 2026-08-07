# `context-window-overflow` — Context Window Overflow Attack Pack

> **OWASP:** LLM10 · **Base impact:** 6/10 · **Impact class:** AVAILABILITY / INTEGRITY · **Requires:** CHAT · **Phase:** 9
> **Catalogue:** [Annex B](../../../../docs/annex-b-attack-catalog.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

What happens at the edges of the context budget — do the application's controls silently fall out of the window?

**Deliberately bounded.** Payload sizes are capped by profile, the rate limiter still applies, and `cost-amplification` is excluded from the quick and standard profiles — available only in `deep`, behind an explicit acknowledgement flag. The intent is to measure a limit, never to exhaust a target.

## Responsibilities

- **Attacks in this pack:**
- prompt-displacement — volume intended to push the system prompt out of scope
- retrieval-saturation — a query retrieving maximal context, crowding out instructions
- truncation-probe — where the application truncates, and what it drops first
- session-history-flood — unbounded growth degrading instruction adherence
- cost-amplification — maximum tokens and latency inducible by one request
- **Detector bindings:** Threshold (0.7-1.0), Differential (0.8-0.9), Canary (1.0), Structural (0.8)
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
