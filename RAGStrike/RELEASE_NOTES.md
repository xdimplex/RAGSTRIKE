# Release notes — v0.3.0 (v1.0 release candidate)

> **Release candidate.** Everything the framework claims to do, it does — and everything it does not
> do is listed rather than omitted. See [`docs/limitations.md`](docs/limitations.md); it is the most
> important document in this release.

---

## What this is

RAGStrike is an extensible offensive security evaluation framework for retrieval-augmented
generation systems. It executes attack packs against a RAG application, analyzes the responses with
deterministic detectors, scores the result with published arithmetic, and produces a report in which
every finding traces back to the exact request, response, detector, and calculation that produced it.

It ships beside a **differential lab** — VulnerableRAG and SecureRAG, two applications identical
except for their security controls — so the scanner's own true-positive and false-positive behaviour
can be measured rather than assumed.

---

## What is in this release

| Subsystem | State |
|---|---|
| Core engine — orchestrator, executor, scheduler, scoring | Complete |
| Plugin framework — manifest-first discovery, nine-method lifecycle | Complete |
| Attack SDK — scaffolding, conformance suite, replay harness | Complete |
| Attack packs — prompt injection, prompt leakage, context poisoning | Complete |
| Evaluation plugins — five, non-offensive | Complete |
| Analyzer engine — rules, confidence, scoring, evidence, recommendations | Complete |
| Reporting engine — HTML, Markdown, JSON | Complete (PDF declared, refusing) |
| Dashboard — nine pages, sixteen components, seven services | Complete as a client |
| Persistence — SQLite, four migrations, three repositories | Complete |
| VulnerableRAG | Complete, nine documented weaknesses |
| SecureRAG | Complete, seven controls |
| Validation harness — benchmarks, consistency, performance | Complete |

**1,326 tests in RAGStrike (including the validation harness), 248 in SecureRAG.** Six
import-linter contracts enforced as a merge gate.

---

## Design commitments this release keeps

These are the properties the architecture was built to guarantee, and each is enforced by something
executable rather than by convention:

**Extension without modification.** A new attack pack requires zero edits under `core/`. A test
asserts no plugin name appears anywhere in engine code — so the promise cannot quietly stop being
true.

**Deterministic, reproducible scoring.** Risk is arithmetic, never a model call. An import-linter
contract forbids `core.scoring` from reaching a model, an adapter, a database, or httpx. Weight
tables are published under a `scoring_model_version`, and trend views refuse cross-version comparison
without an explicit recompute.

**Honest uncertainty.** `INCONCLUSIVE` is a first-class outcome. A target that ignored a payload, an
empty response, or a detector with no reference to calibrate against all produce INCONCLUSIVE rather
than a confident PASS. Coverage is reported beside every grade.

**Authorization is a record, not a checkbox.** No scan starts without one, and it is carried into
every report. Targets are loopback-only by default, and reaching anything else takes two independent
deliberate steps.

**Data, never code.** Payloads, detector bindings, analyzer rules, poisoning datasets, and report
templates are all data. Report templates use `string.Template` rather than Jinja — which is already
installed — because a template is a file an operator edits, and a templating language that can
execute turns styling a report into a code-execution surface.

---

## Not in this release

Named here because a release that quietly drops a limitation is worse than one that never claimed it.

- **The `/api/v1` server.** The dashboard is a complete client of it; without a backend every page
  shows an honest `BACKEND OFFLINE` state. The CLI reaches the full engine directly.
- **PDF rendering.** Declared and refusing rather than emitting an empty file.
- **`ragstrike report` CLI command.** Reports are generated through the Python API.
- **Eight of twelve catalogued attack packs.**
- **Adapters other than `fastapi`.**
- **Rate limiting, authentication, and authorization in SecureRAG** — declared, excluded from the
  chain by construction, and named in `GET /health` as not implemented.
- **Plugin sandboxing.** Packs run with full process trust. An accepted risk, not an oversight.

---

## Versions

| | |
|---|---|
| `VERSION`, `__version__`, `CITATION.cff` | **0.3.0** |
| `PLUGIN_API_VERSION` | **1.0.0** |
| `pyproject.toml` `version` | **0.1.0** |

The two version numbers move independently by design (ADR-015): an application patch release must
not signal a potential break to every third-party pack author.

`pyproject.toml` is **deliberately left at 0.1.0**. This is a release candidate that has never been
published, and bumping the packaging version would imply a distribution history that does not exist.
It is bumped at the tag, not before.

---

## Upgrading

There is nothing to upgrade from. On first run, migrations apply automatically.

---

## Verifying this release

```bash
pytest && lint-imports && ruff check . && black --check .
python -m validation.runner --checks-only
```

And, with the lab pair running and seeded with the same corpus:

```bash
python -m validation.runner --targets vulnerable-rag secure-rag
```

The results of that run against this build are recorded in
[`docs/validation-results.md`](docs/validation-results.md) — **including the fact that the full
differential was not completed on this hardware.** The scan loop is proven end to end against both
live targets; the headline claim (VulnerableRAG grades badly, SecureRAG grades cleanly) needs hours
of model inference per target and is not yet demonstrated. That is stated there rather than implied
away.

---

## Known issues

**`mypy src` reports 11 pre-existing errors** in `plugins/`, `core/`, `cli/`, and `database/` —
untyped parameters and two unreachable branches. They predate the current subsystems and are recorded
rather than suppressed. Per-subsystem `mypy` on everything added in Phases 10–12 is clean.

**`lint-imports` can be blocked by Windows Smart App Control**, which refuses to load `grimp`'s
native extension. This is an OS policy rather than a project defect; CI is unaffected.

**Scan duration is dominated by target model inference.** On a local 4B model on CPU a full scan
takes tens of minutes. The validation harness separates framework time from target time.

---

## Thanks

Standards referenced: OWASP Top 10 for LLM Applications, MITRE ATLAS, CWE. See
[`docs/third-party-attribution.md`](docs/third-party-attribution.md).
