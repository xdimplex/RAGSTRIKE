# Retrieval Consistency Evaluation

**Evaluation plugin — not an attack.** Slug `retrieval-consistency`. Severity on failure: **LOW**.

## What it asks

Ask the same question three times — do the same documents come back?

## How it works

Repeats an identical question and compares the retrieved source sets. Ordering differences are ignored; only the set matters.

## What a FAIL means

Retrieval is unstable, so every other finding in the report is a single sample rather than a measurement — a PASS may be luck and a FAIL may be noise.

## Why this is non-offensive

It asks one ordinary question several times. The only thing it stresses is determinism.

## Test cases

6, in 2 groups of 3 repeats. They live in [`payloads/cases.yaml`](payloads/cases.yaml), not in the code — adding a case
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
retrieval_consistency/
├── metadata.yaml        identity, compatibility, least-privilege permissions
├── plugin.py            the criterion (139 lines)
├── payloads/cases.yaml  the test cases
└── README.md            this file
```

## Related

- OWASP mapping: —
- [`docs/evaluation-plugins.md`](../../docs/evaluation-plugins.md) — the family, the outcome
  vocabulary, and how to write your own
- [`docs/plugin-development.md`](../../docs/plugin-development.md) — the underlying `BaseAttack`
  contract
