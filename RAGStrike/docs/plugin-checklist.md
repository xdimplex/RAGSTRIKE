# Plugin checklist

Before you ship a pack. Each item is a question with a right answer, not a box to tick.

---

## Manifest

- [ ] `slug` is unique, lowercase, hyphenated
- [ ] `version` follows semver
- [ ] `requires_api` names the plugin API you actually tested against (currently `1.0`)
- [ ] `category` is one an operator would search for
- [ ] `severity` is the *worst* this pack can report, not the typical case
- [ ] `requires` lists every capability you use — **missing one means a runtime failure instead of a
      clean SKIP**
- [ ] `permissions` is empty unless you genuinely need network or filesystem access

## Payloads

- [ ] In `payloads/*.yaml`, not in Python
- [ ] Every payload declares `destructive: false` — or the pack documents why not
- [ ] Nothing writes to the target
- [ ] A canary proves success without extracting anything real
- [ ] Payload text is safe to print in a report and in a log

## Behaviour

- [ ] `payloads()` is deterministic — same input, same order, every run
- [ ] `analyze()` is pure. No network, no clock, no randomness
- [ ] `cleanup()` runs even when `execute()` raised, and is safe to run twice
- [ ] `health()` never raises
- [ ] **`INCONCLUSIVE` is returned when the pack cannot tell**, and PASS only when it actually
      checked

## Evidence

- [ ] Every FAIL carries the request, the response, and the detector that fired
- [ ] Evidence is redacted, not omitted — a finding without evidence is an assertion
- [ ] No credential, canary value, or document text reaches a log line

## Honesty

- [ ] The pack documents what it **cannot** establish
- [ ] Confidence is capped when a detector is uncalibrated
- [ ] No finding claims more than the evidence supports

## Tests

- [ ] A test for the attack succeeding
- [ ] A test for the attack **failing against a hardened target** — the one most packs skip
- [ ] A test for the INCONCLUSIVE path
- [ ] Tests run with no network and no model

## Gate

```bash
ragstrike plugins validate <slug>
pytest
```

## Documentation

- [ ] A README saying what it tests, what it cannot, and how to read its findings
- [ ] OWASP / ATLAS / CWE identifiers where they apply
- [ ] Every recommendation is actionable — names a change, not a principle
