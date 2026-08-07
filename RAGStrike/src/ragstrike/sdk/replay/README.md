# `sdk.replay` — Replay Harness

> **Layer:** cross-cutting · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Re-runs the analyzer over stored evidence with no target contact. **Strategically the most important module in the SDK.**

Detector quality is where a scanner lives or dies, and iterating detectors against a live LLM is slow, costly, and nondeterministic. Because evidence is immutable and detectors are pure, detector development becomes a fast offline deterministic unit-test loop over real recorded responses — the same insight that made packet-capture replay central to network IDS development.

## Responsibilities

- Load stored probes for a scan and re-run any detector set.
- Diff new signals against recorded ones, so a detector change shows its exact blast radius.
- Back the golden regression tier over the committed evidence corpus.

## Files that will exist here later

- `harness.py`

## This folder must NEVER contain

- Contacting a target. Replay is offline by definition.
- Mutating stored evidence.
