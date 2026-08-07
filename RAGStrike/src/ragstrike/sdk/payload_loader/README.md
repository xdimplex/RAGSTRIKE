# `sdk.payload_loader` — Lenient Payload Loading

> **Layer:** cross-cutting (development-time) · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md) · **Guide:** [`docs/sdk-guide.md`](../../../../docs/sdk-guide.md)
> **Status:** implemented — Phase 5.

## Purpose

`SdkPayloadLoader` — loads every payload file in a directory, skipping (not raising on) individually malformed ones. Wraps Phase 4's `PayloadLoader`, which is strict by design; this is the lenient, development-time alternative the Phase 5 brief specifies.

## Responsibilities

- Support the same formats as the Phase 4 loader: `.yaml`/`.yml`/`.json`/`.txt`.
- Parse each file independently via `PayloadLoader.parse_file()` (added to the Phase 4 loader specifically for this), so one bad file cannot mislabel or block another.
- Report what was skipped and why, via `LoadResult.skipped`.

## Key exports

| Name | What it is |
|---|---|
| `SdkPayloadLoader` | Lenient loader. `.load()` for full detail, `.all()` for just the payloads. |
| `LoadResult` | `payloads: list[Payload]`, `skipped: list[SkippedPayloadFile]`. |
| `SkippedPayloadFile` | One malformed file and the reason it was skipped. |

## This folder must NEVER contain

- Duplicated parsing logic — this delegates to Phase 4's `PayloadLoader` for every format rule rather than reimplementing YAML/JSON/TXT handling a second time.
