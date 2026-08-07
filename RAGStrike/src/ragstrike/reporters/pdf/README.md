# `reporters.pdf` — PDF Renderer (deferred)

> **Layer:** 3 — Infrastructure  ·  **SDD reference:** [Annex C §C.1](../../../../docs/annex-c-adrs.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Placeholder for PDF output, deferred to Phase 11. HTML and JSON are the v1 contract. This folder exists now to prove the point: adding a third format requires a new renderer here and no change to any computation. If implementing PDF ever requires touching `core/`, the renderer abstraction has failed.

## Responsibilities

- Render the same ReportModel to paginated PDF.
- Reuse the HTML templates via an HTML-to-PDF path rather than maintaining a second layout.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `renderer.py` | ReportModel → PDF bytes | 11 |

## This folder must NEVER contain

- A parallel report model or a second source of truth for layout.
- A hard dependency added to the base install — PDF belongs behind an optional extra.
