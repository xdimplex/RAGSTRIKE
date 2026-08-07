> ⚠️ **This repository is an intentionally vulnerable application built for security testing.**
> It must never be deployed anywhere reachable. See [`docs/LAB_SAFETY.md`](../docs/LAB_SAFETY.md).

# `profiles` — Application Profiles

> **Profile scope:** the two applications  ·  **SDD reference:** [ADR-009](../../RAGStrike/docs/annex-c-adrs.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The two thin applications built on the shared core.

- **`vulnerable/`** — VulnerableRAG. Constructs `SecurityPolicyChain([])`. The chain is empty **in code, by construction** — not via a configuration flag, so no misconfiguration can accidentally harden it.
- **`secure/`** — SecureRAG. Constructs the full control chain.

Same functionality, same UI, same corpus, same model. Only the chain differs.

## Responsibilities

- Compose the policy chain for each profile.
- Own the system prompt for each profile: weak and secret-bearing for vulnerable, structured and secret-free for secure.
- Own port assignment: vulnerable on 9000/8601, secure on 9001/8602.
- Provide the entry points for API and UI.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `vulnerable/profile.py` | SecurityPolicyChain([]) — empty by construction | 2 |
| `vulnerable/prompts/system_prompt.txt` | Weak template with SYNTHETIC canary-tagged secrets | 2 |
| `secure/profile.py` | Full control chain | 11 |
| `secure/prompts/system_prompt.txt` | Structured, delimited, no secrets | 11 |

## This folder must NEVER contain

- A real credential in either system prompt. Lab secrets are synthetic, high-entropy, canary-tagged, and clearly labelled, so a real leak can never be confused with a lab artifact.
- Functional differences between the profiles beyond the policy chain — `tests/parity/` exists to catch exactly this.
- Shared mutable state between profiles.
