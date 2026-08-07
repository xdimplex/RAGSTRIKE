# `cli` — Command Line Interface (Layer 4)

> **Layer:** 4 — Interface  ·  **SDD reference:** [SDD §23](../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

A first-class interface with full parity to the API, because CI pipelines and headless servers are primary consumers — not an afterthought. The CLI calls the same orchestrator the API calls; neither duplicates the other's logic.

## Responsibilities

- Provide the command set in SDD §23: `doctor`, `targets`, `packs`, `scan`, `scans`, `report`, `compare`, `replay`, `sdk`.
- Return distinct exit codes so a pipeline can tell 'the app is insecure' from 'the scanner is misconfigured' — those demand opposite responses.
- Offer human (Rich) and JSON output modes.
- Render live progress from the event bus.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `main.py` | Typer application | 3 |
| `commands/*.py` | One module per command group | 3–6 |
| `output/human.py` | Rich rendering | 3 |
| `output/json_out.py` | Machine-readable output | 3 |
| `exit_codes.py` | 0 ok · 1 threshold exceeded · 2 config · 3 unreachable · 4 errored · 5 unauthorized | 3 |

## This folder must NEVER contain

- Logic the API does not also have — parity is a requirement (FR-18).
- Interactive prompts in a path a CI pipeline uses.
- `print()` — use the output modules so JSON mode stays clean.
