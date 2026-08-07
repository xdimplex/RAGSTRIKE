# `sdk.constants` — Framework-Wide Constants

> **Layer:** cross-cutting (development-time) · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md) · **Guide:** [`docs/sdk-guide.md`](../../../../docs/sdk-guide.md)
> **Status:** implemented — Phase 5.

## Purpose

Default timeout, retry count, retry backoff, default headers, framework/plugin-API version re-exports, payload tier names, and `plugins.yaml` key names — the numbers a plugin gets if it does not think about them, mirroring the engine's own defaults.

## Responsibilities

- Re-export `FRAMEWORK_VERSION` and `SDK_PLUGIN_API_VERSION` from the `ragstrike` package root, so plugin code does not reach into the package root directly.
- Declare `DEFAULT_TIMEOUT_S`, `DEFAULT_RETRY_COUNT`, `DEFAULT_RETRY_BACKOFF_S`, `DEFAULT_RETRY_MAX_BACKOFF_S`, `DEFAULT_HEADERS` — matching `core/config/models.py`'s own defaults where an equivalent exists.
- Declare `PAYLOAD_TIERS` and `ConfigKeys` — namespaced string constants, not enums, because both are used as dict keys against YAML-sourced data.

## Key exports

| Name | What it is |
|---|---|
| `FRAMEWORK_VERSION, SDK_PLUGIN_API_VERSION` | Re-exported version constants. |
| `DEFAULT_TIMEOUT_S, DEFAULT_RETRY_*` | Defaults matching the engine's own. |
| `PAYLOAD_TIERS, ConfigKeys` | Namespaced string constants. |

## This folder must NEVER contain

- A value that silently overrides an operator's `plugins.yaml` setting. These are fallback defaults only — `configs/plugins.yaml` always wins when it sets a value.
