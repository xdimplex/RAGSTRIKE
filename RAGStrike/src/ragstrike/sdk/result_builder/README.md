# `sdk.result_builder` — Standard Result Construction

> **Layer:** cross-cutting (development-time) · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md) · **Guide:** [`docs/sdk-guide.md`](../../../../docs/sdk-guide.md)
> **Status:** implemented — Phase 5.

## Purpose

`ResultBuilder` builds one `AttackResult` per payload — the standard shape the Phase 5 brief specifies (plugin name, payload id, payload, target, timing, status, evidence, severity, confidence, recommendation, references, notes). `fold_results()` combines many into the one `Analysis` the engine's contract requires; `pick_recommendation()` does the matching job for the separate `recommendation()` method.

## Responsibilities

- Provide a fluent builder for `AttackResult`, including `.from_execution_record()` to seed identity, timing, and baseline evidence from an `ExecutionRecord` in one call.
- Fold a `list[AttackResult]` into one `Analysis` with a fixed outcome precedence (FAIL > ERROR > PASS > SKIPPED) and an averaged confidence.
- Pick the recommendation to surface for a folded result set, preferring the highest-ranked outcome present.

## Key exports

| Name | What it is |
|---|---|
| `ResultBuilder` | Fluent builder → `AttackResult`. |
| `fold_results` | `list[AttackResult] -> Analysis`. The engine-facing translation point. |
| `pick_recommendation` | `list[AttackResult] -> Recommendation | None`. |

## This folder must NEVER contain

- A second engine contract. `AttackResult` never crosses into the engine — only the `Analysis` that `fold_results()` produces does.
