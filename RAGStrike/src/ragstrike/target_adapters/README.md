# `target_adapters` — Target Adapter Layer (Layer 3)

> **Layer:** 3 — Infrastructure  ·  **SDD reference:** [SDD §12](../../../docs/SDD.md), [ADR-008](../../../docs/annex-c-adrs.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The only place in the codebase that knows what a target actually is. This is what delivers goal G3: the attack engine never learns whether it is talking to Ollama, OpenAI, LangChain, or bespoke Python. Every adapter implements the `TargetAdapter` port plus whichever capability protocols it genuinely supports.

## Responsibilities

- Translate between the engine's `TargetRequest`/`TargetResponse` and the provider's wire format.
- Declare capabilities honestly — the scheduler trusts them, and an overstated capability produces meaningless skipped-case accounting.
- Preserve the raw provider payload as evidence.
- Implement session reset where the provider supports it (R-03 depends on this working).
- Pass the SDK adapter conformance suite — that suite is how Liskov substitutability is enforced rather than assumed.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `<adapter>/adapter.py` | One adapter per subfolder | 3–12 |

## This folder must NEVER contain

- Attack logic, payload construction, or response interpretation.
- Being imported by `core/` — adapters are injected at the composition root.
- Declaring a capability it does not fully support.
