# `reporters.json` — JSON Renderer

> **Layer:** 3 — Infrastructure  ·  **SDD reference:** [SDD §19](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Renders the ReportModel to machine-readable JSON — the interface for CI pipelines, dashboards, and downstream tooling.

## Responsibilities

- Emit a stable, versioned schema; a consumer written against v1 must keep working.
- Preserve full fidelity: every field the HTML report shows must be present.
- Embed engine version, pack versions, scoring model version, and content hash (NFR-12).

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `renderer.py` | ReportModel → JSON bytes | 6 |
| `schema.json` | Published JSON Schema for the report format | 6 |

## This folder must NEVER contain

- Schema changes without a version bump.
- Lossy output — JSON is the fidelity reference, HTML is the presentation.
