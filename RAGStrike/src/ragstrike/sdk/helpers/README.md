# `sdk.helpers` — Stateful / I/O-Adjacent Helpers

> **Layer:** cross-cutting (development-time) · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md) · **Guide:** [`docs/sdk-guide.md`](../../../../docs/sdk-guide.md)
> **Status:** implemented — Phase 5.

## Purpose

Timer, UUID generation, file/JSON/YAML reading, and async retry with backoff — the reusable plumbing named in the Phase 5 brief. Split from `sdk.utils`: everything here touches the filesystem, the clock, or a random source; `utils` never does.

## Responsibilities

- `Timer` — a stopwatch, usable as a context manager.
- `new_uuid` / `new_short_id` — id generation matching the engine's own convention (`uuid.uuid4().hex`).
- `FileHelper` — text/bytes reading that raises `SdkError` instead of bare `OSError`.
- `JsonHelper` / `YamlHelper` — parse-that-fails-safely, plus file load/dump.
- `retry_async` — exponential backoff for a plugin's own I/O inside `execute()`. Retries **exceptions only**, never response content — see `retry.py` for why that distinction matters to the scoring model.

## Key exports

| Name | What it is |
|---|---|
| `Timer` | Stopwatch context manager. |
| `new_uuid, new_short_id` | Id generation. |
| `FileHelper, JsonHelper, YamlHelper` | Safe-failure file/format helpers. |
| `retry_async` | Exponential backoff for async I/O. |

## This folder must NEVER contain

- A retry that resends a payload because the *response* looked wrong — that would corrupt the `successes/attempts` exploitability measurement. Retry transport failures only.
