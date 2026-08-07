# `sdk` — Attack SDK (Developer Kit)

> **Layer:** cross-cutting (development-time) · **SDD:** [`docs/SDD.md`](../../../docs/SDD.md) · **Guide:** [`docs/sdk-guide.md`](../../../docs/sdk-guide.md)
> **Status:** implemented — Phase 5.

## Purpose

What turns "we have a plugin contract" into "a real attack is under 100 lines." Every plugin
already gets `BaseAttack` (Phase 3/4) for free — five required methods, a handful of optional
lifecycle hooks, dependency injection via `PluginContext`. The SDK is everything a real attack
needs *on top of that contract* so a plugin author writes metadata, payloads, and a success
criterion, and nothing else: request construction, response parsing, standardized result
bookkeeping, reusable validation, and the small utilities every plugin was otherwise going to
reinvent.

**No attacks live here.** This phase builds the toolkit; Phases 7–10 build the attacks that use it.
`examples/custom_pack/` demonstrates the SDK with a plugin that sends one benign question and
asserts nothing about security.

## The eleven modules

| Module | What it gives a plugin |
|---|---|
| [`base/`](base/README.md) | `BasePayload`, `BaseRecommendation` (re-exports of the engine's own types), `BaseResult`, `BaseEvidence` |
| [`context/`](context/README.md) | `ScanContext` — the scan-time companion to `PluginContext` |
| [`request_builder/`](request_builder/README.md) | `TargetRequestBuilder` — fluent `TargetRequest` construction |
| [`response_parser/`](response_parser/README.md) | `ResponseParser` — named extraction over `TargetResponse` |
| [`payload_loader/`](payload_loader/README.md) | `SdkPayloadLoader` — lenient loading; skips malformed files instead of raising |
| [`result_builder/`](result_builder/README.md) | `ResultBuilder`, `fold_results`, `pick_recommendation` |
| [`validators/`](validators/README.md) | Reusable, attack-agnostic response/field/JSON checks |
| [`helpers/`](helpers/README.md) | `Timer`, id generation, file/JSON/YAML helpers, `retry_async` |
| [`utils/`](utils/README.md) | `StringUtils`, `FormattingUtils` — pure, stateless |
| [`exceptions/`](exceptions/README.md) | SDK exception hierarchy, all rooted in `RAGStrikeError` |
| [`constants/`](constants/README.md) | Default timeout/retry/headers, version re-exports, config keys |
| [`interfaces/`](interfaces/README.md) | `Protocol` definitions for the SDK's own building blocks |

## Dependency injection, still

Nothing in the SDK changes Phase 4's rule: **plugins never instantiate the database, the logger,
the target adapter, the configuration, the scheduler, or the engine.** `PluginContext` remains the
one way a plugin receives configuration and a bound logger. `ScanContext` extends that at
scan-time (target, scan id) by being *assembled by the plugin from information it already has*
inside `execute()` — not by changing `BaseAttack`'s signature, which this phase may not do.

## A complete attack, using the SDK

```python
class MyAttack(BaseAttack):
    plugin_id = "my-attack"
    plugin_version = "1.0.0"
    category = "example"

    def payloads(self):
        return SdkPayloadLoader(self.context.payload_dir).all()

    async def execute(self, target, payloads):
        records = []
        for payload in payloads:
            request = TargetRequestBuilder().with_prompt(payload.content).build()
            response = await target.chat(request)
            records.append(ExecutionRecord(payload.id, payload.content, response))
        return records

    def analyze(self, records):
        results = [
            ResultBuilder(plugin_name=self.plugin_name, target="t")
            .from_execution_record(r).passed().build()
            for r in records
        ]
        return fold_results(results)

    def recommendation(self, analysis):
        return Recommendation(title="...", remediation="...")
```

Metadata, payloads, a success criterion. See `examples/custom_pack/plugin.py` for the real,
runnable, sub-100-line version, and `docs/sdk-guide.md` for the full guide with diagrams.

## This folder must NEVER contain

- Being imported by `core/`, `scheduler/`, `plugins/registry/`, or `plugins/loader/` at runtime —
  the SDK depends on the engine, never the reverse. Enforced by `.importlinter` (contract 1: the
  SDK sits directly above `ragstrike.plugins` in the layer stack; nothing below it may import up).
- A second engine contract. Everything here composes around `BaseAttack`/`Analysis`/`Payload`/
  `Recommendation`; nothing replaces them.
- Attack logic. This phase builds the toolkit, not a scanner.
