> ⚠️ **This repository is an intentionally vulnerable application built for security testing.**
> It must never be deployed anywhere reachable. See [`docs/LAB_SAFETY.md`](../docs/LAB_SAFETY.md).

# `corpus` — Reference Document Corpus

> **Profile scope:** identical for both profiles  ·  **SDD reference:** [SDD §32](../../RAGStrike/docs/SDD.md), [Annex A §A.2](../../RAGStrike/docs/annex-a-directory-structures.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The fixed document set both profiles ingest. **Identical for both** — same PDFs, same order, same chunking. Any difference here invalidates the differential test.

`manifest.yaml` declares provenance for every document and chunk source. RAGStrike's retrieval-integrity pack verifies returned chunks against this manifest, so the manifest is not documentation — it is test infrastructure.

## Responsibilities

- `benign/` — ordinary documents: handbook, FAQ, policy document.
- `poisoned/` — pre-staged attack documents for teaching, each explained in the folder's own README.
- `manifest.yaml` — declared provenance enabling retrieval-integrity verification.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `benign/*.pdf` | Ordinary corpus documents | 2 |
| `poisoned/*.pdf` | Pre-staged teaching attacks with documented payloads | 2 |
| `manifest.yaml` | Provenance declaration | 2 |

## This folder must NEVER contain

- Real company documents, real personal data, or real credentials.
- A document present in one profile's corpus and not the other's.
- Poisoned documents ingested by default — they are staged for deliberate exercises, not loaded at startup.
