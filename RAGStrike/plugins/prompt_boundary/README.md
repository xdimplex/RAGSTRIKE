# Prompt Boundary Evaluation

**Evaluation plugin — not an attack.** Slug `prompt-boundary`. Severity on failure: **HIGH**.

## What it asks

If someone simply asks the assistant what it was told to do, does it say?

## How it works

Asks about the assistant's own setup, then checks the reply against a list of generic system-prompt phrasings. It does not attempt extraction — it asks politely, once.

## What a FAIL means

System configuration and user conversation share a channel; the prompt is reachable as dialogue.

## Why this is non-offensive

The evidence records which phrase matched, never the surrounding text — proof of a leak should not become a second copy of the leaked material.

## Test cases

4 (including one control case using an ordinary corpus question). They live in [`payloads/cases.yaml`](payloads/cases.yaml), not in the code — adding a case
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
prompt_boundary/
├── metadata.yaml        identity, compatibility, least-privilege permissions
├── plugin.py            the criterion (68 lines)
├── payloads/cases.yaml  the test cases
└── README.md            this file
```

## Related

- OWASP mapping: LLM06
- [`docs/evaluation-plugins.md`](../../docs/evaluation-plugins.md) — the family, the outcome
  vocabulary, and how to write your own
- [`docs/plugin-development.md`](../../docs/plugin-development.md) — the underlying `BaseAttack`
  contract
