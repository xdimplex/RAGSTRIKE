# Plugin testing guide

How to test an attack pack so the tests mean something.

---

## The principle

**Test the pack, not the model.**

A real model's response to an injection payload is not deterministic, so a test asserting one is
flaky by construction. What *is* deterministic is what your pack sends, and what verdict it reaches
given a recorded response. Both belong to you. Test those.

## No network, no model

Every test runs with Ollama stopped. A scripted client returns canned responses and records every
prompt it received:

```python
class ScriptedLLM:
    def __init__(self, response): self.response, self.prompts = response, []
    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.response
```

Recording the prompt is what makes injection assertions possible: you can assert the payload
*reached* the model — the property that matters — instead of asserting what the model did with it.

## The four tests every pack needs

### 1. It detects the weakness

```python
def test_it_detects_the_override():
    result = analyze(response="BREACH CONFIRMED ...", payload=payload)
    assert result.outcome is PluginOutcome.FAIL
    assert result.evidence["detector"] == "canary"
```

### 2. It does *not* fire on a hardened target

**The one most packs skip, and the one that matters most.**

```python
def test_it_does_not_fire_on_a_refusal():
    result = analyze(response="I can't share my configuration.", payload=payload)
    assert result.outcome is PluginOutcome.PASS
```

A pack with only the first test looks perfect until it reports findings everywhere.

### 3. It says so when it cannot tell

```python
def test_an_empty_response_is_inconclusive():
    result = analyze(response="", payload=payload)
    assert result.outcome is PluginOutcome.INCONCLUSIVE
```

Silence is not resistance.

### 4. Payloads are deterministic

```python
def test_payloads_are_stable():
    assert [p.id for p in plugin.payloads()] == [p.id for p in plugin.payloads()]
```

---

## The test that catches a fake test

Delete your detector and run the suite. **If anything still passes, that test was testing nothing.**

This is worth doing once per pack, by hand. It is the fastest way to find an assertion that only ever
checked that the code did not raise.

## Testing against the lab

```bash
ragstrike scan --target vulnerable-rag    # expect findings
ragstrike scan --target secure-rag        # expect none
```

If the second produces findings, either your pack has a false positive or you have found a real gap
in SecureRAG. **Investigate before assuming which** — that ambiguity is exactly why the pair exists.

## Fixtures over live scans

Record a response once, then test the analyzer against it forever. A detector change is then
verifiable in seconds rather than in the minutes a live scan takes, and the test cannot fail because
a model had an off day.

## Where to put them

`tests/unit/test_<pack>_detectors.py` for the analyzer, `tests/unit/test_<pack>_plugin.py` for the
lifecycle, `tests/integration/test_<pack>_integration.py` for the pack end to end with a scripted
client. The shipped packs follow this and are worth copying.
