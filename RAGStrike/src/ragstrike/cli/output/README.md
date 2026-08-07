# `cli.output` — Output Rendering

> **Layer:** Layer 4 · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Two rendering modes: Rich for humans, JSON for machines. Isolated here so that JSON mode is guaranteed parseable — a stray print() elsewhere would corrupt it.

## Responsibilities

- human.py — Rich tables, progress bars, highlighted evidence spans.
- json_out.py — stable machine-readable output.
- Apply the redaction policy before anything reaches a terminal.

## Files that will exist here later

- `human.py`
- `json_out.py`

## This folder must NEVER contain

- Bare print() calls.
- Formatting decisions duplicated in command modules.
