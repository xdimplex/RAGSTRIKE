# `sdk.response_parser` — Response Extraction

> **Layer:** cross-cutting (development-time) · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md) · **Guide:** [`docs/sdk-guide.md`](../../../../docs/sdk-guide.md)
> **Status:** implemented — Phase 5.

## Purpose

`ResponseParser` — named extraction methods over `TargetResponse`: text, JSON, chunks, sources, citations, metadata, status code, headers, latency, error. Every method is honest about what the shipped adapter actually captures; nothing here invents data.

## Responsibilities

- Wrap one `TargetResponse` and expose `.text()`, `.json()`, `.chunks()`, `.sources()`, `.citations()`, `.metadata()`, `.status_code()`, `.headers()`, `.latency_ms()`, `.error()`, `.ok()`, `.excerpt()`.
- Document every best-effort extraction (`status_code`, `headers`, `citations`) with exactly what it falls back to and when it returns nothing, rather than pretending certainty the data does not support.

## Key exports

| Name | What it is |
|---|---|
| `ResponseParser` | Wraps one `TargetResponse`; stateless beyond that. |

## This folder must NEVER contain

- Attack-specific interpretation — this extracts facts, it does not decide whether an attack worked. That is the plugin's own `analyze()`.
