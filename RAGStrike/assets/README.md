# `assets` — Static Assets

> **Layer:** documentation  ·  **SDD reference:** [SDD §19](../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Project imagery: logo, documentation screenshots, and report assets. Kept out of the package so the wheel stays small.

## Responsibilities

- `logo/` — project marks in SVG and PNG.
- `screenshots/` — dashboard and report captures for the README and docs site.
- `report_assets/` — source files for imagery inlined into rendered reports.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `logo/ragstrike.svg` | Primary mark | 11 |
| `screenshots/*.png` | Documentation captures | 11 |

## This folder must NEVER contain

- Screenshots containing real target data, real endpoints, or unredacted evidence.
- Large binaries that belong in a release artifact rather than in git history.
