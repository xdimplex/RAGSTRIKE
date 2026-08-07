# RAGStrike

**An offensive security evaluation framework for RAG systems** — with a vulnerable lab and a hardened
one, so that a finding can be proved rather than asserted.

---

## The problem

A RAG pipeline has an attack surface that a chatbot does not: retrieved documents enter the prompt.
Anyone who can get text into the corpus can get text into the model's instructions.

Existing tooling mostly asks "did the model say something bad?" That question conflates two very
different situations — a control that worked, and a test that failed to fire. **A scanner that cannot
tell you which one you are looking at is worse than no scanner**, because it produces confidence
either way.

## What RAGStrike does

Runs attack packs against a RAG target, analyses the responses with deterministic detectors, and
produces a report where every finding names the request, the response, and the rule that fired.

Then it does the thing that makes the result checkable: **the same packs run against a hardened
target.** A pack that fires on both is measuring something other than the control it claims to
measure, and the differential says so.

## Three claims, and how each is checked

**Findings are explainable.** Risk scoring is deterministic and the arithmetic is reproduced in the
report. Not a number handed down — the calculation, written out, so a reader can redo it by hand.

**Coverage is reported beside every grade.** A grade from 40% coverage and one from 100% must not
render identically, and they do not. Every skip records a reason.

**Uncertainty is a first-class result.** `INCONCLUSIVE` exists and is used. "The target resisted" and
"nobody knows" are different claims and are never merged.

## What it does not do

**No real attack findings have been produced yet.** The framework is built, tested, and instrumented;
the full differential run against the live lab pair is a multi-hour job that has not been completed.
[`validation-results.md`](../docs/validation-results.md) records exactly that.

**`/api/v1` is a scaffold**, so the dashboard shows `BACKEND OFFLINE` or clearly-labelled demo data.

**Plugins are not sandboxed.** Installing an attack pack grants it the trust of installing a Python
package, because it is one.

The full list is [`limitations.md`](../docs/limitations.md), and it is the most important page in the
documentation.

## Safety

**Local targets only, by default.** `127.0.0.1` and `localhost`. Every scan requires a persisted
authorization record — not a checkbox at run time (ADR-017). No pack writes to a target.

Scanning a system you do not own is not a configuration question.

---

```bash
pip install -e .
ragstrike targets --verify              # targets live in configs/targets.yaml
ragstrike scan --target vulnerable-rag
```

[Quick start](quickstart.md) · [Architecture](architecture.md) · [Features](features.md) ·
[FAQ](faq.md) · [Roadmap](roadmap.md)

---

*v1.0.0 · Apache-2.0 · Python 3.11+*
