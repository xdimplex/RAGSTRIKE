# `attacks` — First-Party Attack Packs

> **Layer:** Plugin (external to the engine by design)  ·  **SDD reference:** [SDD §13](../../../docs/SDD.md), [Annex B](../../../docs/annex-b-attack-catalog.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The twelve packs shipped with RAGStrike. **None of them is special-cased in the engine.** They register through the same public entry-point mechanism third parties use — dogfooding that guarantees the extension path is real rather than aspirational. If any pack here were deleted, the engine would still start, still scan, and still report, with a coverage gap recorded.

## Responsibilities

- One subfolder per pack, each with `pack.yaml`, `attacks/`, `payloads/`, `detectors/`, `recommendations/`.
- Payloads are **data, never code** — YAML templates rendered by a non-evaluating engine (ADR-016).
- Every attack declares required capabilities, detector bindings with weights, impact class, base impact, attempt count, and OWASP/ATLAS/CWE mapping.
- Every pack ships conformance tests and must be validated in both directions: detects on VulnerableRAG, silent on SecureRAG.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `<pack>/pack.yaml` | Manifest: compatibility, capabilities, permissions | 7–10 |
| `<pack>/attacks/*.yaml` | Attack definitions | 7–10 |
| `<pack>/payloads/*.yaml` | Payload sets by tier | 7–10 |
| `<pack>/detectors/*.yaml` | Detector bindings; custom detectors only where built-ins fall short | 7–10 |
| `<pack>/recommendations/catalog.yaml` | Remediation entries owned by this pack | 7–10 |

## This folder must NEVER contain

- Importing private core internals — packs use `sdk/` and `plugins/base/` only.
- Executable payloads.
- Destructive payloads. Every first-party payload declares `destructive: false` and the conformance suite enforces it.
- A pack that fires on SecureRAG — that is a false positive and a merge blocker, not a feature.
