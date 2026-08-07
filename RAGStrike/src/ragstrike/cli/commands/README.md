# `cli.commands` — Command Modules

> **Layer:** Layer 4 · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

One module per command group. Each parses arguments, calls the orchestrator, and renders — exactly the same orchestrator the API calls.

## Responsibilities

- doctor, targets, packs, scan, scans, report, compare, replay, sdk.
- Map outcomes onto the exit-code table so a pipeline can distinguish 'the app is insecure' from 'the scanner is misconfigured' — those demand opposite responses.

## Files that will exist here later

- `doctor.py`
- `targets.py`
- `scan.py`
- `report.py`
- `compare.py`
- `replay.py`
- `sdk.py`

## This folder must NEVER contain

- Logic the API lacks — parity is a requirement.
- Interactive prompts in any path a CI pipeline uses.
