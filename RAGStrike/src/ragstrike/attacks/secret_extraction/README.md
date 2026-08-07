# `secret-extraction` — Secret Extraction Attack Pack

> **OWASP:** LLM02, LLM07 · **Base impact:** 10/10 · **Impact class:** CONFIDENTIALITY · **Requires:** CHAT · **Phase:** 8
> **Catalogue:** [Annex B](../../../../docs/annex-b-attack-catalog.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Does the application disclose credentials, keys, endpoints, or internal configuration? Highest base impact in the catalogue — a leaked credential is an immediate, transferable compromise.

**Entropy gating is essential here.** The Pattern detector combines format regexes with a Shannon-entropy threshold and a known-placeholder deny-list (`AKIAIOSFODNN7EXAMPLE`, documentation samples). Without it, secret detectors flood any corpus containing example configuration — and a scanner that cries wolf on credentials gets switched off.

## Responsibilities

- **Attacks in this pack:**
- direct-credential-request — asks for keys, tokens, connection strings
- configuration-enumeration — environment variables, endpoints, internal hostnames
- error-induced-disclosure — verbose errors carrying configuration
- corpus-secret-harvest — secrets accidentally present in the corpus
- partial-reconstruction — extracted in fragments to evade output filters
- format-evasion — spelled out, reversed, or base64-encoded to bypass masking
- **Detector bindings:** Pattern (0.8-1.0), Canary (1.0), Similarity (0.7), Retrieval Integrity (0.8)
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
