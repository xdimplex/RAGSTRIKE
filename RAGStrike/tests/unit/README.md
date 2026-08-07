# `tests.unit` — Unit Tests

> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Pure functions, no I/O, the whole tier under 30 seconds. Mirrors the source tree: one test module per source module.

The scheduler and scoring packages are held to a higher coverage bar than the rest, because bugs there are invisible in output — a whole pack silently unscheduled looks exactly like 'no findings'.

## Responsibilities

- Cover scheduler expansion, scoring arithmetic, detectors, config merge, and template rendering.
- Run with no network, no database, and no filesystem beyond `tmp_path`.
- Stay fast enough that nobody is tempted to skip them.

## Files that will exist here later

- `domain/`
- `scheduler/`
- `scoring/`
- `analyzers/`
- `config/`
- `registry/`

## This folder must NEVER contain

- I/O of any kind.
- A test that needs a live LLM.
- Shared state between tests.
