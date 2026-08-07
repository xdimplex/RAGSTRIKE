# RAGStrike — summary

**A security testing framework for AI systems that answer questions from documents.**

Python · ~20,000 lines · 251 modules · 1,327 tests · Apache-2.0

---

## The problem, without jargon

Many AI products answer questions by first looking things up in a company's documents, then feeding
what they found to the model. The catch: the model cannot reliably tell the difference between *the
documents* and *its instructions*. Anyone who can slip text into the document store can slip
instructions into the AI.

## What was built

**Three things, not one.**

1. **RAGStrike** — the scanner. Runs attack techniques against such a system and reports what worked,
   with evidence.
2. **VulnerableRAG** — a deliberately insecure lab system to attack.
3. **SecureRAG** — the same system, hardened.

The third is the interesting one. Running the same test against both is what proves the test works: if
an attack succeeds against both, the test is broken, not the target. Most security tools have no way
to check themselves.

## Engineering practices

- **The architecture is enforced by the build.** Six layering rules are checked automatically; a
  violation fails CI. This is not a diagram that drifts from the code.
- **24 architecture decision records.** Every significant decision written down with the alternatives
  that were rejected. One was later reversed — and because the original reasoning survived, the
  reversal was a decision rather than an accident.
- **Extensible without modification.** A new attack module needs zero changes to the framework, and a
  test fails if anyone violates that.
- **Known problems are published, not hidden.** The audit reports eleven type-checker errors and an
  incomplete validation run. All of it could have been silenced in an afternoon. It is written down
  with cost estimates instead.

## The judgement calls worth mentioning

**Uncertainty is reported as uncertainty.** The tool has a status meaning "I could not tell" and uses
it, rather than reporting "secure" when a test simply failed to fire. False confidence is worse than
no result.

**Coverage is shown beside every grade.** A scan that examined 40% of a system must not look like one
that examined all of it.

**Findings are reproducible by hand.** The risk score's arithmetic is printed in the report, so a
reader can check it rather than trust it.

## Honest status

**The framework is complete and tested. No real vulnerabilities have been found yet** — the full
validation run takes hours on the available hardware and has not been completed. This is stated in the
project's own documentation, in the same words.

## Skills demonstrated

Software architecture and its enforcement · AI/LLM security · Python (FastAPI, Streamlit, asyncio,
pydantic) · plugin systems · test design · technical writing · security judgement under uncertainty ·
disciplined delivery across 15 sequential phases

---

*Full documentation in [`docs/`](../). Start with [`limitations.md`](../limitations.md) — what it does
not do, which is the page that shows how the rest was written.*
