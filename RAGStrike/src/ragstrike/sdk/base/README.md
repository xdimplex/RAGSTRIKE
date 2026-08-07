# `sdk.base` — Base Classes

> **Layer:** cross-cutting (development-time) · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md) · **Guide:** [`docs/sdk-guide.md`](../../../../docs/sdk-guide.md)
> **Status:** implemented — Phase 5.

## Purpose

The four base classes the Phase 5 brief specifies: `BasePayload`, `BaseRecommendation`, `BaseResult`, `BaseEvidence`. `BasePayload` and `BaseRecommendation` are re-exports of the engine's own `Payload` and `Recommendation` types (Phase 3/4) — not new types, since the engine already fixed what a payload and a recommendation are. `BaseResult` (`AttackResult`) and `BaseEvidence` are new: the standard per-payload result shape and the structured-fact accumulator, both introduced by this phase.

## Responsibilities

- Re-export `Payload` as `BasePayload`, `Recommendation` as `BaseRecommendation` — zero behavioural difference from the engine types, just SDK-facing names.
- Define `AttackResult` (`result.py`): the standard shape every plugin's `analyze()` builds internally, per payload, before folding into the engine's `Analysis`.
- Define `BaseEvidence` and `EvidenceCollection` (`evidence.py`): one structured fact per record, folded into `Analysis.evidence` as an ordinary dict.

## Key exports

| Name | What it is |
|---|---|
| `BasePayload` | = `ragstrike.plugins.base.attack.Payload` |
| `BaseRecommendation` | = `ragstrike.plugins.base.attack.Recommendation` |
| `BaseResult / AttackResult` | Standard per-payload result. See `sdk.result_builder`. |
| `BaseEvidence / EvidenceCollection` | One structured fact; a collection of them. |

## This folder must NEVER contain

- A type that diverges from the engine type it re-exports — the whole point is that `BasePayload(...)` constructs exactly what the scheduler already accepts.
- Anything the engine (`core/`, `scheduler/`, `plugins/registry`, `plugins/loader`) imports.
