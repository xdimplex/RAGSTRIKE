# Context Separation Evaluation

**Evaluation plugin — not an attack.** Slug `context-separation`. Severity on failure: **HIGH**.

## What it asks

When text arrives as content — a passage to summarize — are instructions inside it followed?

## How it works

Supplies a passage containing an embedded directive and asks for a summary. A system with clean separation summarizes the passage, directive and all.

## What a FAIL means

Anything reaching the context window can steer the model — the mechanism behind indirect injection.

## Why this is non-offensive

The passage is supplied inline in the question rather than planted in the corpus. Planting it would mean writing to the system under test; inline reaches the same question without mutating anything.

## Test cases

4 (including one control case with no embedded directive). They live in [`payloads/cases.yaml`](payloads/cases.yaml), not in the code — adding a case
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
context_separation/
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
