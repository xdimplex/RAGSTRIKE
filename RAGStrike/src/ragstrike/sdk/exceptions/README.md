# `sdk.exceptions` — SDK Exception Hierarchy

> **Layer:** cross-cutting (development-time) · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md) · **Guide:** [`docs/sdk-guide.md`](../../../../docs/sdk-guide.md)
> **Status:** implemented — Phase 5.

## Purpose

Every SDK-raised exception descends from `ragstrike.core.errors.RAGStrikeError`, so nothing raised through the SDK escapes the CLI's exit-code mapping or the scheduler's per-plugin isolation guard. This extends the Phase 3/4 taxonomy; it does not replace it.

## Responsibilities

- `PayloadError` — payload parsing failures the lenient loader could not recover from.
- `ValidationError` — a `sdk.validators` `require_*` check failed.
- `TargetConnectionError` / `PluginTimeoutError` — SDK-facing synonyms for the engine's own `TargetUnreachableError` / `TargetTimeoutError`, so plugin code reads naturally.
- `PluginConfigurationError` — a plugin's own `context.config` is invalid.

## Key exports

| Name | What it is |
|---|---|
| `SdkError` | Base for SDK-raised errors with no closer existing home. |
| `PayloadError, ValidationError` | New concepts the engine had no name for. |
| `TargetConnectionError, PluginTimeoutError` | SDK-facing synonyms for existing core errors. |
| `PluginConfigurationError` | A plugin's own config is malformed. |

## This folder must NEVER contain

- A second, disconnected exception hierarchy. Every class here `isinstance`-checks true against the matching `ragstrike.core.errors` type wherever one already exists.
- A class literally named `TimeoutError` — see `exceptions.py` for why that shadows the builtin and what this module does instead.
