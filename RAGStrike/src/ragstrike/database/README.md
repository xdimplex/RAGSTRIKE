# `database` — Persistence (Layer 3)

> **Layer:** 3 — Infrastructure  ·  **SDD reference:** [SDD §20](../../../docs/SDD.md), [ADR-007](../../../docs/annex-c-adrs.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

aiosqlite persistence behind repository interfaces declared in `core/contracts/`. Raw parameterized SQL, no ORM: the schema is small and stable, and the queries in a security tool must stay reviewable.

**Embeddings are never stored here.** SQLite has no vector index; storing embeddings in it means full scans over float blobs — the worst of both stores. Embeddings live in ChromaDB, in the VulnerableRAG repository, not in RAGStrike at all.

## Responsibilities

- Manage the aiosqlite connection and pragmas.
- Implement one repository per aggregate, returning **domain entities**, never raw rows.
- Run numbered, checksum-verified, forward-only migrations. A checksum mismatch is a fail-fast startup error, because silently running against an unexpected schema corrupts history.
- Enforce evidence immutability structurally: the probe repository exposes no update or delete method, so immutability is a type-level guarantee rather than a rule people remember.
- Apply the retention policy — full evidence for the last N scans per target, older scans compacted.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `connection.py` | Connection management and pragmas | 3 |
| `mappers.py` | Row ↔ domain entity — the only module that knows both shapes | 3 |
| `retention.py` | Compaction of old scans | 6 |

## This folder must NEVER contain

- Embeddings or vectors of any kind.
- Leaking a row, cursor, or SQL string outward — repositories return domain entities.
- An UPDATE or DELETE against `probes` outside scan-deletion cascade.
- An editable migration. Once released, a migration is immutable; correct it with a new one.
