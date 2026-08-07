# `profiles.vulnerable.prompts` — System Prompt

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The deliberately weak system prompt: retrieved context concatenated with no delimiters, no provenance labelling, and no instruction-hierarchy language — plus synthetic credentials that should never be in a prompt at all.

## Responsibilities

- Demonstrate weaknesses V1, V4, and V5 in a single artifact.
- Carry synthetic, high-entropy, **canary-tagged** secrets so any leak is provable and no real credential could ever be mistaken for one.

## Files that will exist here later

- `system_prompt.txt`

## This folder must NEVER contain

- A real credential, endpoint, or hostname.
- A secret that is not canary-tagged — an untagged leak is undetectable with certainty.
