# `examples/custom_pack` — SDK Walkthrough (`ExampleAttack`)

> **Status:** implemented — Phase 5. See [`docs/sdk-guide.md`](../../docs/sdk-guide.md) for the
> full guide.

## What this is

`ExampleAttack`, a complete, runnable plugin built entirely on the Attack SDK — **99 lines**,
under the Phase 5 acceptance criterion. It loads a payload, sends it through
`TargetRequestBuilder`, reads the response with `ResponseParser`, and returns a standardized
result via `ResultBuilder` and `fold_results()`.

**It is not a security attack.** It sends one benign question and reports what came back. It
asserts nothing about whether a target is vulnerable to anything.

## Why it lives here, not in `plugins/`

`PluginRegistry` only scans `plugins.local_dirs` (`./plugins` and `./packs` by default).
`examples/` is not one of them, so `ExampleAttack` is never discovered, never appears in
`ragstrike plugins list`, and never runs as part of a scan. It exists purely to be read and to be
exercised directly by `tests/unit/test_sdk_example_attack.py`.

For the reference plugin the registry *does* discover — which also exercises the full extended
lifecycle (`setup`/`healthcheck`/`cleanup`) — see [`plugins/dummy_attack/`](../../plugins/dummy_attack/).

## Files

| File | Purpose |
|---|---|
| `metadata.yaml` | Manifest — not read by anything, since this pack is never discovered. Documents the shape a real manifest would have. |
| `plugin.py` | `ExampleAttack`. Read this first. |
| `payloads/example.yaml` | One benign payload, loaded via `SdkPayloadLoader`. |

## Reading it

Open `plugin.py`. Three methods matter:

- `payloads()` — one line: `SdkPayloadLoader(self.context.payload_dir).all()`.
- `execute()` — builds a request with `TargetRequestBuilder`, calls `target.chat()`, records an
  `ExecutionRecord`. The only method here with `await` in it.
- `analyze()` — reads each response with `ResponseParser`, builds one `AttackResult` per payload
  with `ResultBuilder`, folds them into an `Analysis` with `fold_results()`.

`recommendation()` is a fixed `Recommendation` — this demo's advice never varies by outcome. A
real plugin would branch on `analysis.outcome`.

## This folder must NEVER contain

- Anything requiring a core change — the whole point is that this plugin needed none.
- Destructive payloads, or anything claiming to test real security properties.
- A manifest change that would let the registry accidentally discover it (it must stay outside
  `plugins/local_dirs`).
