# Example: a custom target

Pointing RAGStrike at a RAG application that is not part of the lab.

## The safety rule first

RAGStrike scans **loopback only** by default, and reaching anything else takes **two independent
deliberate steps**:

```yaml
# configs/config.yaml
safety:
  allow_remote_targets: true                    # step 1
  allowed_hosts: ["localhost", "127.0.0.1", "::1", "rag.internal.example"]   # step 2
```

Either alone is refused. The check lives in `target_adapters.build_adapter`, so every path — scan,
`targets --verify`, any future caller — passes through it and none can skip it.

**Only do this for a system you are authorized to test.** The authorization block below is not
paperwork; no scan starts without it, and it is carried into every report, so a report always says
who authorized the testing that produced it.

## The target definition

See [`targets.yaml`](targets.yaml). The `fastapi` adapter is **configuration-driven**: request
shaping and response extraction are declared as field names and dotted paths, so supporting a
different bespoke API is an edit to this file rather than a new adapter.

| Option | Answers |
|---|---|
| `chat_path` | Which endpoint takes a question |
| `prompt_field` | Which JSON key the question goes in |
| `answer_path` | Where to read the answer from |
| `chunks_path` | Where retrieved chunks are, if exposed |
| `sources_path` | Where citations are, if exposed |
| `session_field` / `session_path` | How to hold a conversation |

## When configuration is not enough

If your API is not JSON-over-HTTP with a single question field — streaming, gRPC, a message queue —
you need an adapter rather than a config change. `src/ragstrike/target_adapters/` has the base class
and four scaffolds; the `fastapi` one is the worked reference.

Implementing `TargetAdapter` is the whole contract. Nothing in the engine changes.

## Capabilities decide what runs

Your adapter declares what the target can do:

| Capability | Unlocks |
|---|---|
| `CHAT` | Everything. The minimum |
| `RETURN_CHUNKS` | Retrieval-integrity and context checks |
| `LIST_SOURCES` | Citation grounding |
| `INGEST_DOCUMENT` | Indirect-injection packs that plant a document |
| `SESSION_MEMORY` | Multi-turn and persistence checks |

A pack needing a capability the target lacks is **`SKIPPED`, and the skip is reported as a coverage
gap.** That matters: a skipped pack finds nothing, and nothing looks clean. Always read coverage
alongside the grade.

## Verify before scanning

```bash
ragstrike targets --verify
```

Probes each target through the real adapter with the real scope policy. If it refuses here, it will
refuse to scan — and the message says which of the two safety steps is missing.
