# `reporters.templates.assets` — Report Assets

> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

CSS and any icons, inlined into rendered reports at build time.

## Responsibilities

- Print-safe, theme-aware stylesheet.
- Everything inlined — a report is emailed and opened offline, so it must render with no network.

## Files that will exist here later

- `report.css`

## This folder must NEVER contain

- A CDN reference, a web font, or a remote image.
- JavaScript required for the report to be readable (NFR-13).
