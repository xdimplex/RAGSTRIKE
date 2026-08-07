# `sdk.utils` — Pure Stateless Utilities

> **Layer:** cross-cutting (development-time) · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md) · **Guide:** [`docs/sdk-guide.md`](../../../../docs/sdk-guide.md)
> **Status:** implemented — Phase 5.

## Purpose

`StringUtils` and `FormattingUtils` — pure functions over strings and numbers. No I/O, no clock, no randomness, safe to call in a tight loop with no side effect but the return value. See `sdk.helpers` for the split rationale.

## Responsibilities

- `StringUtils` — truncate, normalize_whitespace, contains_any/contains_all, slugify.
- `FormattingUtils` — human_duration, human_bytes, percentage.

## Key exports

| Name | What it is |
|---|---|
| `StringUtils` | truncate, normalize_whitespace, contains_any, contains_all, slugify. |
| `FormattingUtils` | human_duration, human_bytes, percentage. |

## This folder must NEVER contain

- Anything with a side effect. The moment a function in this package touches a file, the clock, or randomness, it belongs in `sdk.helpers` instead.
