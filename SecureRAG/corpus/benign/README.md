# `corpus/benign` — Benign Documents

> > ⚠️ Part of an **intentionally vulnerable** application. Local lab only — see `docs/LAB_SAFETY.md`.
> **Scaffold only** — Phase 1 creates structure, not behaviour.
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Ordinary synthetic documents that both profiles ingest identically. The baseline against which poisoning is measured.

## Responsibilities

- Company handbook, product FAQ, policy document — all synthetic.
- Declared in `../manifest.yaml` with a checksum, which is what makes retrieval-integrity verification possible.

## Files that will exist here later

- `company_handbook.pdf`
- `product_faq.pdf`
- `policy_document.pdf`

## This folder must NEVER contain

- Real company documents or real personal data.
- A document ingested by one profile and not the other.
