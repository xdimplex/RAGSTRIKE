# `utils` — Pure Helpers (Layer 0)

> **Layer:** 0 — Pure helpers  ·  **SDD reference:** [SDD §36](../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Small, pure, dependency-free helpers used across layers: text normalization, entropy calculation, hashing, SemVer comparison, path handling, time formatting.

This folder is under permanent suspicion. A `utils` package is where architecture goes to die — every module that does not obviously belong somewhere gets dumped here until the package is the real centre of the system. The rule below is enforced in review.

## Responsibilities

- Host genuinely generic, stateless, side-effect-free functions.
- Stay importable from any layer without creating a dependency violation, which is only possible because it imports nothing but the standard library.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `text.py` | Unicode normalization, zero-width stripping, tokenization | 6 |
| `entropy.py` | Shannon entropy — gates the secret detector's false positives | 8 |
| `hashing.py` | Content hashing for report integrity | 6 |
| `semver.py` | Version range comparison for plugin compatibility | 4 |

## This folder must NEVER contain

- Anything domain-specific. If it mentions a scan, a finding, or an attack, it belongs in a domain package.
- State, I/O, or configuration access.
- Third-party imports.
- A module named `helpers.py`, `misc.py`, or `common.py`.
