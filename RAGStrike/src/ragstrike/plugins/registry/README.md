# `plugins.registry` — Registry & Compatibility

> **Layer:** 2 — Application  ·  **SDD reference:** [SDD §13.5–13.6](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Decides policy: which discovered packs are compatible, which activate, which are refused, and what the user is told about each.

## Responsibilities

- Resolve declared SemVer ranges against `PLUGIN_API_VERSION`.
- Activate compatible packs; refuse incompatible ones with an actionable message.
- Resolve duplicate-slug conflicts by version and record the shadowed pack.
- Expose an immutable catalog to the scheduler and a health report to the dashboard and to the report's Coverage section.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `plugin_registry.py` | Discovery policy and activation | 4 |
| `compatibility.py` | SemVer range resolution | 4 |
| `health.py` | Per-pack health and refusal reasons | 4 |
| `detector_registry.py` | Built-in plus pack-contributed detectors | 4 |
| `renderer_registry.py` | Report format registry | 6 |

## This folder must NEVER contain

- Discovery mechanics — that is `loader/`. Registry decides policy; loader finds files.
- Executing attacks.
- Hiding a refusal. Every refused pack appears in the health report and in the Coverage section.
