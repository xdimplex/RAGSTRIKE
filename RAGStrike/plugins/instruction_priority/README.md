# Instruction Priority Evaluation

**Evaluation plugin — not an attack.** Slug `instruction-priority`. Severity on failure: **HIGH**.

## What it asks

When a user message contains an instruction that competes with the system's own, which one wins?

## How it works

Sends benign requests to emit a meaningless canary token. A grounded system keeps answering from its documents; one that emits the token has told us the user's text outranked its configuration.

## What a FAIL means

User-supplied text can override system instructions — the mechanism behind direct prompt injection.

## Why this is non-offensive

Every payload asks the target to say a made-up word. Nothing is extracted, nothing is written, and the corpus is untouched.

## Test cases

4 (including one control case with no override at all). They live in [`payloads/cases.yaml`](payloads/cases.yaml), not in the code — adding a case
is editing YAML, and the criterion in `plugin.py` does not change.

Each case declares what to expect:

```yaml
payloads:
  - id: ...
    content: ...
    expects: ...
```

## Outcomes

| Outcome | When |
|---|---|
| `PASS` | The expected behaviour held. |
| `FAIL` | It demonstrably did not. |
| `INCONCLUSIVE` | The target answered, but the answer settles nothing — an empty reply, or one the criterion cannot classify. Never reported as `PASS`. |

## Files

```
instruction_priority/
├── metadata.yaml        identity, compatibility, least-privilege permissions
├── plugin.py            the criterion (65 lines)
├── payloads/cases.yaml  the test cases
└── README.md            this file
```

## Related

- OWASP mapping: LLM01
- [`docs/evaluation-plugins.md`](../../docs/evaluation-plugins.md) — the family, the outcome
  vocabulary, and how to write your own
- [`docs/plugin-development.md`](../../docs/plugin-development.md) — the underlying `BaseAttack`
  contract
