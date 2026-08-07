# `sdk.request_builder` — Request Construction

> **Layer:** cross-cutting (development-time) · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md) · **Guide:** [`docs/sdk-guide.md`](../../../../docs/sdk-guide.md)
> **Status:** implemented — Phase 5.

## Purpose

`TargetRequestBuilder` — fluent construction of `TargetRequest`, the one request shape the current target contract defines (`chat()`). There is no GET/POST in RAGStrike's target contract because a plugin never makes its own HTTP call; the adapter mediates all network access.

## Responsibilities

- Build `TargetRequest` objects: prompt, session, timeout, correlation id — all fields the shipped `FastAPIAdapter` actually reads.
- Stage headers/cookies/auth into `TargetRequest.metadata`, honestly documented as **not yet consumed** by the shipped adapter (`FastAPIAdapter.chat()` never reads `metadata`).
- Declare `HttpMethod` and `RawRequestSpec` as **architecture only** — a documented shape for a future raw-HTTP attack capability that does not exist yet and requires a new `Capability` value and adapter method this phase may not add.

## Key exports

| Name | What it is |
|---|---|
| `TargetRequestBuilder` | Fluent builder → `TargetRequest`. |
| `HttpMethod, RawRequestSpec` | Documented, unwired placeholders for future work. |

## This folder must NEVER contain

- A plugin-facing way to issue raw HTTP. All network access stays behind the injected `TargetAdapter` (Phase 4's dependency-injection rule).
