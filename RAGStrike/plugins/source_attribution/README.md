# Source Attribution Verification

**Evaluation plugin — not an attack.** Slug `source-attribution`. Severity on failure: **MEDIUM**.

## What it asks

Are the citations real — does every cited source appear among the chunks actually retrieved?

## How it works

Asks ordinary corpus questions and inspects the structured retrieval fields on the reply. This is a correctness check on the system's own bookkeeping.

## What a FAIL means

Attribution is generated rather than grounded — indistinguishable to a reader from the real thing, which is what makes it dangerous.

## Why this is non-offensive

It asks ordinary questions and reads structured response fields. Nothing else.

## Test cases

3 (including one unanswerable question, where citing nothing is the correct behaviour). They live in [`payloads/cases.yaml`](payloads/cases.yaml), not in the code — adding a case
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
source_attribution/
├── metadata.yaml        identity, compatibility, least-privilege permissions
├── plugin.py            the criterion (102 lines)
├── payloads/cases.yaml  the test cases
└── README.md            this file
```

## Related

- OWASP mapping: LLM09
- [`docs/evaluation-plugins.md`](../../docs/evaluation-plugins.md) — the family, the outcome
  vocabulary, and how to write your own
- [`docs/plugin-development.md`](../../docs/plugin-development.md) — the underlying `BaseAttack`
  contract
