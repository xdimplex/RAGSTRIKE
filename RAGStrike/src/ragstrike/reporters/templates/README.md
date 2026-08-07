# `reporters.templates` — Report Templates

> **Layer:** 3 — Infrastructure  ·  **SDD reference:** [SDD §19.2](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Jinja2 templates and inlined assets for rendered reports.

## Responsibilities

- `report.html.j2` — the master template covering all ten sections.
- `partials/` — one partial per section, so sections are independently reviewable.
- `assets/` — CSS and any icons, inlined at render time.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `report.html.j2` | Master document template | 6 |
| `partials/*.j2` | Per-section partials | 6 |
| `assets/report.css` | Print-safe, theme-aware stylesheet | 6 |

## This folder must NEVER contain

- Logic beyond presentation — no scoring, no filtering, no sorting decisions in a template.
- External asset references.
