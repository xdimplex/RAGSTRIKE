# `configs` — Configuration Files

> **Layer:** configuration  ·  **SDD reference:** [SDD §21](../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

All runtime configuration as YAML. No configuration lives in code beyond typed defaults, and no secrets live here.

## Responsibilities

- `ragstrike.yaml` — installation defaults, the second precedence level.
- `profiles/` — quick, standard, deep scan profiles (pack selection, payload tiers, concurrency, seed).
- `targets/` — example target definitions including the required authorization block.
- `scoring/` — versioned category weight tables. A weight change requires a version bump and a changelog entry.
- `recommendations/` — the remediation catalog.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `ragstrike.yaml` | Installation defaults | 1 |
| `profiles/{quick,standard,deep}.yaml` | Scan profiles | 1 |
| `targets/*.example.yaml` | Example targets — examples only, never real endpoints | 1 |
| `scoring/v1_0_0.yaml` | Scoring model weights | 6 |
| `recommendations/catalog.yaml` | Remediation catalog | 6 |

## This folder must NEVER contain

- Secrets, API keys, or credentials. Those come from the environment; `.env` is gitignored.
- Real production endpoints in committed examples.
- An unversioned change to a scoring weight.
