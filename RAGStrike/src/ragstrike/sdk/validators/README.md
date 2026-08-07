# `sdk.validators` — Reusable Validation Helpers

> **Layer:** cross-cutting (development-time) · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md) · **Guide:** [`docs/sdk-guide.md`](../../../../docs/sdk-guide.md)
> **Status:** implemented — Phase 5.

## Purpose

Attack-agnostic checks every plugin needs before it can start deciding whether a payload succeeded: does a response exist, is a status code in range, does JSON parse, are required fields present. Two styles: `is_*`/`has_*` predicates that never raise, and `require_*` assertions that raise `ValidationError` naming exactly what failed.

## Responsibilities

- Provide response, status-code, JSON, field-presence, and plugin-config-key checks.
- Never make a judgment call specific to any attack category — that stays in the plugin's own `analyze()`.

## Key exports

| Name | What it is |
|---|---|
| `response_exists / require_response` | Response presence. |
| `is_valid_status_code / require_valid_status_code` | Status code range check. |
| `is_valid_json / require_valid_json` | JSON parseability. |
| `fields_exist / missing_fields / require_fields` | Dict key presence. |
| `has_required_metadata / require_metadata` | Plugin config key presence. |

## This folder must NEVER contain

- A check for a specific attack technique (a canary string, an injection marker). That is attack-specific and belongs in the plugin, never here.
