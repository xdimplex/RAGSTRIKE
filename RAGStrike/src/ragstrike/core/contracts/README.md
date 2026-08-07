# `core.contracts` — Ports (Layer 1)

> **Layer:** 1 — Ports  ·  **SDD reference:** [SDD §12](../../../../docs/SDD.md), [§13](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Every abstraction the engine talks through. These protocols are the seams that make the mandated stack replaceable and make third-party extension possible without core edits. This package contains declarations only — zero logic.

## Responsibilities

- `TargetAdapter` — the sole view the engine has of a system under test (SDD §12.1).
- Capability protocols — `SupportsChat`, `SupportsIngest`, `SupportsRetrievalIntrospection`, `SupportsSessionReset` (Interface Segregation).
- `AttackPlugin`, `Detector`, `Mutator`, `PayloadSource` — the plugin-facing contracts.
- `Renderer` — report output formats.
- Repository protocols — one per aggregate.
- `EventBus` — progress publication.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `target_adapter.py` | Base adapter protocol: describe, health_check, chat, close | 3 |
| `capability_protocols.py` | Narrow optional capability protocols | 3 |
| `attack_plugin.py` | Pack-facing contract (ADR-002/003) | 4 |
| `detector.py` | Pure `(Probe, DetectorConfig, ScanContext) -> Signal` | 4 |
| `repositories.py` | Repository protocols — note: probe repository exposes no update/delete | 3 |
| `renderer.py` | ReportModel -> bytes | 6 |

## This folder must NEVER contain

- Implementations — a default method body is a design smell here.
- Imports from any outer layer.
- Fat interfaces with optional methods raising `NotImplementedError` (ADR-008 rejects this).
