# `profiles.secure.prompts` — Hardened System Prompt

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The reference prompt template: explicit role hierarchy, retrieved context wrapped in unambiguous delimiters and labelled as untrusted data, and a standing instruction that context is reference material and never instruction.

## Responsibilities

- Counter weaknesses V1 and V5.
- Contain no credentials at all — secrets are externalized, and masking is defence in depth rather than the only line.

## Files that will exist here later

- `system_prompt.txt`

## This folder must NEVER contain

- Any secret, synthetic or otherwise.
- Context concatenated without a delimiter.
