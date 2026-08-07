# `rag.ingestion.loaders` — Document Loaders

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Format-specific extraction. PDF for v1.

## Responsibilities

- Extract text from PDFs — **including metadata fields**, which is precisely the surface the metadata-injection attack targets.
- Preserve zero-width and control characters. Stripping them is a control (V2).

## Files that will exist here later

- `pdf_loader.py`

## This folder must NEVER contain

- Normalization or filtering of extracted content.
