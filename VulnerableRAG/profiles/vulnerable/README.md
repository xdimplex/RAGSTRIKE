# `profiles.vulnerable` — VulnerableRAG

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The insecure application. Constructs `SecurityPolicyChain([])` — **empty in code, by construction**, not via a configuration flag, so no misconfiguration can accidentally harden it and silently invalidate every scan result.

## Responsibilities

- Compose the empty policy chain.
- Own the weak system prompt containing synthetic canary-tagged secrets.
- Bind API 9000, UI 8601, loopback only.
- Refuse to start without `RAGSTRIKE_LAB_ACK=1`.

## Files that will exist here later

- `profile.py`
- `main_api.py`
- `main_ui.py`
- `config.yaml`
- `prompts/system_prompt.txt`

## This folder must NEVER contain

- Any security control.
- A real credential.
- A configuration option that enables a control.
