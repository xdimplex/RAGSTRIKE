# `scheduler` — Attack Scheduler (Layer 2, pure)

> **Layer:** 2 — Application (pure functions)  ·  **SDD reference:** [SDD §15.1](../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Decides *what* to run. Given a profile, a target descriptor, and the pack catalog, it produces an ordered immutable `ScanPlan`. It performs no I/O whatsoever, which is what makes it exhaustively unit-testable without a target — and scheduling bugs matter, because a whole pack silently unscheduled looks exactly like 'no findings'.

## Responsibilities

- Select packs and attacks enabled by profile and configuration.
- Filter by target capability and record every exclusion with a reason (SDD §12.2).
- Expand attack × payload × variable bindings × mutators × attempts.
- Order deterministically from `profile.seed` — reproducible, but not front-loaded by pack.
- Apply budget caps and log every truncation explicitly as a coverage gap.
- Topologically sort cases carrying `depends_on` (ingest-then-query attacks).

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `planner.py` | The expansion pipeline | 3 |
| `capability_filter.py` | Capability gating with recorded reasons | 3 |
| `variant_expander.py` | Payload × variables × mutators | 4 |
| `budget.py` | Caps with explicit truncation logging | 3 |
| `ordering.py` | Seeded shuffle and topological sort | 3 |
| `plan.py` | Immutable ScanPlan | 3 |

## This folder must NEVER contain

- Any I/O — no network, no database, no filesystem.
- Silently dropping a case. Every exclusion is recorded and reported.
- Non-deterministic ordering.
