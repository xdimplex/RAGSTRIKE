# `reporters.html` — HTML Renderer

> **Layer:** 3 — Infrastructure  ·  **SDD reference:** [SDD §19](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Renders the ReportModel to a self-contained HTML document — the primary human-facing artifact.

## Responsibilities

- Render via Jinja2 templates from `../templates/`.
- Inline all CSS and assets: a report must render with no network access, because it will be emailed and opened offline.
- Remain readable without JavaScript, printable, and legible in light and dark (NFR-13).
- Highlight matched evidence spans so a finding can be verified at a glance.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `renderer.py` | ReportModel → HTML bytes | 6 |

## This folder must NEVER contain

- External CDN references, web fonts, or remote images.
- Computation — the model arrives fully resolved.
- Unredacted secrets when the policy is not `none`.
