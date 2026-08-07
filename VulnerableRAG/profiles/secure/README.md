# `profiles.secure` — SecureRAG

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The hardened twin. Identical functionality, identical UI, identical corpus, identical model — differing only in composing the full control chain.

## Responsibilities

- Compose every control in `rag/policy/controls/`.
- Own the structured, delimited, secret-free system prompt.
- Bind API 9001, UI 8602, loopback only.
- Produce **zero** RAGStrike findings — that is its acceptance criterion, and it is what makes the scanner's false-positive rate measurable.

## Files that will exist here later

- `profile.py`
- `main_api.py`
- `main_ui.py`
- `config.yaml`
- `prompts/system_prompt.txt`

## This folder must NEVER contain

- A functional difference from the vulnerable profile. Only controls may differ.
- A partially composed chain — every implemented control must be in it.
