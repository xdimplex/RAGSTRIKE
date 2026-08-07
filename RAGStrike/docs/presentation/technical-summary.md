# Technical summary

For an engineer who is going to ask hard questions. The answers are here, including the unflattering
ones.

---

## Shape

**RAGStrike** — evaluation framework. 251 modules, 19,805 code lines, 110 packages, Python 3.11+.
**VulnerableRAG** / **SecureRAG** — the lab pair: identical corpus, identical HTTP surface, opposite
security posture.

FastAPI · Streamlit · ChromaDB · aiosqlite · Ollama · pydantic · LangChain splitters.

## Architecture

Clean Architecture, four layers, dependencies inward. **Enforced by `import-linter`: six contracts,
build fails on violation.**

Two traps, both hit in practice:

- **Same-row modules are siblings and may not import each other.** They are peers, not a stack.
- **Indirect chains break contracts.** `reporters` → `analyzers` → `models` broke contract 3 with no
  individually suspicious import. Found by writing a probe module and reading the linter's answer
  rather than reasoning about it, and fixed by extracting a shared record type.

`grimp` reads the AST, so deferring an import into a function body hides it from the runtime, not from
the contract.

## Plugins

Manifest-first discovery (ADR-003): the registry reads `metadata.yaml` and decides compatibility and
capability fit **before importing plugin code**. An incompatible pack is refused with a reason instead
of imported and crashed.

Nine-method lifecycle. Two invariants carry the weight:

- **`payloads()` is deterministic** — the basis of scan reproducibility
- **`analyze()` is pure** — no network, clock, or randomness, which is what allows recorded evidence to
  be re-analysed offline after a detector change, without re-attacking anything

Payloads are YAML, never Python (ADR-016): reviewable by a non-programmer, never evaluated, and
deterministic.

**Zero framework edits for a new pack**, enforced by a test asserting no plugin slug appears in engine
code. That test is why the demo fixture plugin is named `reference-diagnostic` rather than reusing a
real slug.

## Scoring

Weighted noisy-OR aggregation with a **capped** LLM judge (ADR-006) — capped because a judge that can
dominate makes a verdict unreproducible.

Weights carry `scoring_model_version`, and changing one requires bumping it. **A target that has not
changed must not change grade because the scanner was upgraded.** Trend views refuse cross-version
comparison without an explicit recompute. Stricter than semver requires, because a weight change is
technically backward-compatible and would otherwise ship invisibly in a patch.

## The five outcomes

`PASS · FAIL · INCONCLUSIVE · ERROR · SKIPPED`, folding `FAIL > ERROR > INCONCLUSIVE > PASS > SKIPPED`.

**`INCONCLUSIVE` is the one that matters.** Absence of detection is not evidence of resistance, and
collapsing the two is the single most common way a scanner produces false confidence.

## Reporting

One model, N renderers. Every computation happens once in the builders; renderers only choose
presentation — so HTML, Markdown, and JSON *cannot* disagree about a scan, because neither computes
anything.

PDF is declared and refuses. Emitting HTML with a `.pdf` extension would look like success and fail
when someone opened it.

## The dashboard problem

Phase 12 specified a dashboard reading live data from `/api/v1`. `/api/v1` turned out to be an empty
scaffold.

Options: implement the API inside the UI phase (merging phases), import the engine from the UI
(breaking ADR-010 permanently), or ship the client against the contract. **Chose the third**, behind a
`BackendTransport` Protocol with an HTTP implementation and a demo implementation.

It reports `BACKEND OFFLINE` rather than silently serving fixtures. A dashboard showing plausible
numbers without saying they are fictional is worse than one showing nothing. ADR-021.

## Bugs worth describing

**Double HTML escaping.** `style()` and `tag()` both escaped, producing `&amp;quot;` in generated CSS.
Escaping applied defensively at two layers is not twice as safe — it is broken. Fixed by escaping once
and documenting that the other does not.

**A compatibility test that could not fail.** `routes_of()` walked `client.app.routes`, silently
returned an empty set, so "no endpoint was added" passed unconditionally. Switched to `/openapi.json`.
A test that cannot fail converts an open question into false assurance.

**A dead form warning.** A non-local-URL warning inside `st.form` could only render *after*
submission, because Streamlit forms do not re-run on input change. Replaced with a static notice plus a
submit-time check.

**Citation extraction ran backwards** into the sentence, flagging every ordinary citation as
ungrounded.

**A partial canary mask.** An uppercase-only body class left the random hex tail unmasked. A partial
mask is not a mask.

**Validation ran after the embedder.** `on_context_assembly` fires post-retrieval, so a 5,000-character
question 500'd the model before any policy hook saw it. Moved the length check to the HTTP boundary;
the residual gap for in-process callers is documented rather than claimed closed.

**`NOT_RUN` reported as `MISMATCH`.** A disabled plugin made the validation summary say the scanner
disagreed with itself. "You disabled some plugins" rendering as "the scanner is broken", in the one
document whose job is to say whether the scanner works. ADR-023.

**The audit cycle detector, three times.** 32 cycles (package and `__init__` treated as separate nodes,
plus submodule fan-out) → 1 (didn't model deferred execution) → 0. An audit that cries wolf gets
ignored, and an ignored audit misses the real finding when one arrives.

**Windows peak memory silently 0.** ctypes `argtypes` undeclared, so the 64-bit `HANDLE` was truncated
and the call failed quietly.

## Measured

| | |
|---|---|
| Tests | 1,327 passing |
| Contracts | 6/6 |
| Import-time cycles | 0 |
| Dead modules | 0 |
| bandit | 0 (six false positives, each justified at the site) |
| ruff / black | clean |
| **mypy** | **11 errors in pre-Phase-10 code** |

The last row is deliberate. Fixing them means editing earlier phases, which the delivery discipline
forbids; they are recorded with an estimate rather than blanket-ignored. ADR-024.

## What is not done

- **No real attack findings.** The full differential is a multi-hour CPU job, not completed
- **`/api/v1` is a scaffold**
- **No plugin sandboxing** — installing a pack is installing a Python package, and the trust model says
  so
- **No PDF renderer**
- **29 packages without a README**

All in [`../technical-debt.md`](../technical-debt.md) with estimates, and in
[`../limitations.md`](../limitations.md).

## The question that gets asked

**"Why not just fix the eleven mypy errors before tagging 1.0?"**

Because the constraint was to not modify completed phases, and the alternative — a blanket ignore —
produces a green board that was made green by suppression. Maintainers learn very quickly whether a
green board means anything, and once they decide it doesn't, the board stops working as a signal at
all. Eleven visible errors with an estimate is the cheaper long-term position.
