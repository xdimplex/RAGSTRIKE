# `tests.sample_reports` — Golden Reports

> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Committed reference report outputs. Renderer changes must diff cleanly against these, which turns 'did the report change?' from a judgment call into a diff.

## Responsibilities

- Golden HTML and JSON reports rendered from a fixed evidence corpus.
- Cover every redaction policy: none, partial, full.
- Cover the edge cases that are easy to break: zero findings, partial coverage, a cancelled scan, a scan with residual canaries.

## Files that will exist here later

- `golden/report.html`
- `golden/report.json`
- `golden/partial_coverage.json`

## This folder must NEVER contain

- A real secret or real personal data, even in a redaction test fixture — synthetic canary-tagged values only.
- An output regenerated to make a failing test pass without review.
