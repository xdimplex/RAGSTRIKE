<div align="center">

# RAGStrike

**An Extensible Offensive Security Evaluation Framework for Retrieval-Augmented Generation Systems**

[![Version](https://img.shields.io/badge/version-1.0.0-blue)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-1327%20passing-green)](docs/project-metrics.md)
[![Coverage](https://img.shields.io/badge/coverage-89.9%25-green)](docs/project-metrics.md)
[![Contracts](https://img.shields.io/badge/import%20contracts-6%2F6-green)](.importlinter)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Code style](https://img.shields.io/badge/code%20style-black-000000)](https://github.com/psf/black)
[![Types](https://img.shields.io/badge/types-mypy%20strict-blue)](https://mypy-lang.org/)

</div>

---

> ### ⚠️ Project status
>
> **v1.0.0 — Phase 15 complete.** Audited, versioned, and prepared for public release. 251 modules,
> 19,805 code lines, 1,327 tests at 89.9% coverage, zero import-time cycles, zero dead modules, six of
> six architectural contracts machine-enforced. [`docs/project-metrics.md`](docs/project-metrics.md)
> has every number with the command that produced it.
>
> **Read this before trusting any result: no real attack findings exist yet.** The framework is
> built, tested, and instrumented, but the full differential run against the live lab pair is a
> multi-hour job on CPU that has not been completed —
> [`docs/validation-results.md`](docs/validation-results.md) and
> [`docs/technical-debt.md`](docs/technical-debt.md) record exactly that. `mypy src` also reports
> eleven pre-existing errors, recorded rather than suppressed ([ADR-024](docs/annex-c-adrs.md)).
>
> **Phase 14 — validation harness.** The
> [validation harness](validation/README.md) runs benchmark datasets against the live lab pair and
> reports what separated the two applications and what did not; ten consistency checks cover
> discovery, configuration, the analyzer, reporting, the database, logging, and the dashboard.
> **Read [`docs/limitations.md`](docs/limitations.md) before trusting any result** — the `/api/v1`
> server, PDF rendering, and eight of twelve catalogued attack packs are not built, and each is
> listed rather than omitted. Release notes: [`RELEASE_NOTES.md`](RELEASE_NOTES.md).
>
> **Phase 13 — SecureRAG.** The hardened twin of VulnerableRAG lives in a sibling repository: the
> same application with seven security controls composed instead of an empty chain, the same API and
> response schemas, and a parity suite that fails the moment the two drift apart.
>
> **Phase 12 — Dashboard operational.** The Streamlit interface lives in
> [`src/ragstrike/dashboard/`](src/ragstrike/dashboard/): nine pages, sixteen components, seven
> services, and a dark/light theme system in which no colour is hardcoded outside `theme/`. It
> **never imports the engine** — ADR-010, machine-enforced by an import-linter contract that catches
> indirect chains too — so it reaches the engine across a process boundary as a client of
> `/api/v1`. That API is not implemented yet, so without a backend every page shows an honest
> `BACKEND OFFLINE` state rather than fabricating data; `RAGSTRIKE_DASHBOARD__TRANSPORT=demo` serves
> a deterministic fixture for review and demonstration, labelled as such on every page. See
> [`docs/dashboard.md`](docs/dashboard.md).
>
> **Phase 11 — Reporting Engine.** Findings now become reports in
> [`src/ragstrike/reporters/`](src/ragstrike/reporters/): HTML, JSON, and Markdown from **one model,
> N renderers**, so every format agrees about the same scan. Adding a format is a class plus a
> registration — nothing in the engine names one. Everything interpolated into HTML is escaped,
> because a report carries model output and retrieved documents, and templates are formatted rather
> than evaluated. PDF is a declared placeholder that refuses rather than producing an empty file.
> See [`docs/reporting-engine.md`](docs/reporting-engine.md).
>
> **Phase 10 — Analyzer Engine.** Raw plugin results become standardized findings in
> [`src/ragstrike/analyzers/`](src/ragstrike/analyzers/). **The analyzer, not the plugin, decides**:
> status, severity, confidence, and risk are re-derived in one place against one configurable rule
> set. A rule can override a plugin's own verdict — a plugin reporting FAIL with no evidence is
> graded INCONCLUSIVE, and the disagreement is recorded. Every score is arithmetic a reader can
> reproduce by hand, never a model call. See [`docs/analyzer-engine.md`](docs/analyzer-engine.md).
>
> **Phase 9 — three attack packs.** Prompt Injection (LLM01), Prompt Leakage (LLM07), and Context
> Poisoning (LLM04/LLM08) ship in [`src/ragstrike/attacks/`](src/ragstrike/attacks/), with detectors
> and test cases declared in YAML rather than code. Each is honest about what it cannot establish:
> leakage caps its confidence with no reference prompt to calibrate against, and context poisoning
> says plainly it cannot prove cross-session persistence. See
> [`docs/prompt-injection-pack.md`](docs/prompt-injection-pack.md),
> [`docs/prompt-leakage-pack.md`](docs/prompt-leakage-pack.md), and
> [`docs/context-poisoning-pack.md`](docs/context-poisoning-pack.md).
>
> **Phase 6 — evaluation plugins.** Five non-offensive plugins in [`plugins/`](plugins/):
> instruction priority, prompt boundary, context separation, source attribution, and retrieval
> consistency. Each returns PASS / FAIL / **INCONCLUSIVE** — the last a first-class outcome,
> because an undetermined result reported as PASS would say "the target resisted" when the truth is
> "nobody knows". See [`docs/evaluation-plugins.md`](docs/evaluation-plugins.md).
>
> **Loopback only, by construction.** RAGStrike refuses any non-loopback target unless you set
> `safety.allow_remote_targets` **and** add the host to `safety.allowed_hosts`. The check lives at
> the single point an adapter is constructed, with restrictive defaults, so it cannot be skipped by
> a call site that forgets it. This is a development and testing configuration: the intended target
> is the local VulnerableRAG instance from Phase 2.
>
> **Nothing here hoards what it finds.** The evaluation plugins use benign inputs. The injection
> pack proves a finding with canary tokens — meaningless strings, so a success extracts nothing.
> The leakage pack cannot avoid handling real prompt text, so it redacts what it records instead.
> Every payload declares `destructive: false`, and nothing writes to the target. Writing a plugin
> or a pack is a copy-and-edit of one directory; nothing in the engine changes. See
> [`docs/plugin-development.md`](docs/plugin-development.md) and
> [`docs/sdk-guide.md`](docs/sdk-guide.md).
>
> The pipeline is end to end: scan → analyze → report, all persisted. The notable gaps are PDF
> rendering (a declared placeholder), a `ragstrike report` CLI command, and the dashboard. See
> [`ROADMAP.md`](ROADMAP.md) for the full sequence, and start with [`docs/SDD.md`](docs/SDD.md) and
> [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## What this is

Burp Suite, OWASP ZAP, Nmap, Nessus, and Trivy each answer one question for one class of system:
*where does this fail, and what should I do about it?* RAGStrike asks that question of
Retrieval-Augmented Generation applications.

It runs a suite of RAG-specific security test cases against a target, decides which of them
succeeded, scores what it found, and produces an evidence-backed report a security engineer can hand
to a developer.

## What this is not

- **Not a defence product.** RAGStrike recommends remediation; it never applies it.
- **Not a chatbot, and not a RAG system.** It is a *client* of RAG systems.
- **Not a model benchmark.** Hallucination and citation checks measure *your application's* grounding
  controls, not a model's leaderboard position.
- **Not an intrusion tool.** There is no WAF evasion, no rate-limit circumvention, and no detection
  avoidance. There never will be. See [`SECURITY.md`](SECURITY.md).

## Why RAG needs its own scanner

Retrieval-Augmented Generation went from research demo to production default in about two years. The
security tooling did not follow, and RAG introduces a failure mode with no pre-LLM equivalent:

**The retrieval channel is an untrusted input channel that looks trusted.** A document in a vector
store is treated by nearly every prompt template as authoritative context. Anyone who can influence
that corpus — through an upload form, a crawled page, a shared drive, a support ticket — can
influence model behaviour. There was no prior mechanism by which *data* reliably became
*instructions*.

Model-level red-teaming benchmarks say nothing about *your* prompt template, *your* chunking
strategy, *your* retrieval filter, or *your* output handler. That is where applied RAG systems
actually fail, and that is what RAGStrike tests.

## The four ideas the design rests on

**1 · Total provider independence.** The attack engine talks through one abstract `TargetAdapter`
port. It never learns whether it is attacking Ollama, OpenAI, Anthropic, LangChain, LlamaIndex, or
bespoke Python. Provider knowledge lives in exactly one directory.

**2 · Attack packs are plugins, not features.** Every attack category is an independently versioned,
`pip`-installable plugin discovered at runtime. Adding the thirteenth category must require zero
changes under `src/ragstrike/core/` — and a CI test installs a fixture pack to prove it.

**3 · Attacking and judging are separate problems.** Generating a payload and deciding whether it
worked have different failure modes. Splitting `Attack` from `Detector` lets N attacks reuse M
detectors, and lets the notoriously hard "did it work?" question be answered by an ensemble of
independent signals instead of one fragile heuristic.

**4 · Scores are arithmetic, not opinion.** Every number in a report comes from a published,
versioned formula over recorded evidence — never from a model call. A reader can reproduce any score
by hand from the report's own Risk Analysis section.

### The oracle problem, and how it is handled

Deciding whether an attack on a natural-language system succeeded is harder than performing it.
There is no exit code, the evidence is prose, and the target is nondeterministic.

RAGStrike's answer is to **plant deterministic ground truth wherever possible**. It mints a
high-entropy canary token and defines success as that token appearing where it never should. This
turns *"did the model leak its instructions?"* — unanswerable — into *"does the response contain
`RS-CANARY-7f3a…`?"* — trivially decidable, with essentially zero false positives, independent of
language, paraphrase, and model.

Where no canary can be planted, a local LLM judge is available. It is off by default, capped at 0.7
confidence, never sufficient on its own, and every finding that depends on it is labelled
*model-assisted*. A scanner whose verdicts change when someone upgrades a model cannot support trend
analysis.

### Two numbers most scanners get wrong

**Exploitability is measured.** LLM failures are stochastic — a single trial is a coin flip, not a
measurement. Every attack declares an attempt count, and the score uses `successes / attempts`.
"Works every time" and "worked once in ten" are different findings.

**Coverage is reported.** A scan that tested 40% of the surface and one that tested 100% both render
as "no findings" unless you force the difference into the report. Every skipped case records a
reason, every grade carries its coverage fraction, and a grade below 60% coverage is stamped
*partial coverage*.

## Companion repository

[**VulnerableRAG**](../VulnerableRAG) is the lab: an intentionally insecure RAG application — DVWA
for retrieval systems — plus **SecureRAG**, its hardened twin. Same functionality, same UI, same
corpus, same model; the only difference is the security policy chain.

Together they form a **differential test harness**. RAGStrike is only correct if it grades
VulnerableRAG catastrophically *and* SecureRAG cleanly. That property is enforced in CI, and it is
the project's primary defence against a scanner that produces confident nonsense.

## Stack

Python 3.11+ · FastAPI · Streamlit · aiosqlite · ChromaDB (lab side) · Ollama + Qwen3 · YAML · pip

Everything is free and runs entirely offline on a laptop. No paid service is required to develop,
test, or operate any part of the system.

## Using it today

```bash
pip install -e ".[dev]"
```
```bash
ragstrike version
```
```bash
ragstrike plugins
```
```bash
ragstrike targets --verify
```
```bash
ragstrike scan
```

`scan` needs a reachable target. Start the companion lab first:

```bash
cd ../VulnerableRAG && RAGSTRIKE_LAB_ACK=1 python -m profiles.vulnerable.main_api
```

Exit codes are distinct on purpose, so a pipeline can tell a finding from a misconfiguration —
those demand opposite responses:

| Code | Meaning |
|---|---|
| `0` | Clean run |
| `1` | A plugin reported the target vulnerable |
| `2` | Configuration error — unknown target, unknown adapter, bad YAML |
| `3` | Target unreachable |
| `4` | The scan itself errored |
| `5` | No authorization record for the target |

## Writing an attack plugin

Adding an attack requires **zero changes anywhere under `src/ragstrike/`**. There is a test that
walks the engine's AST to prove no plugin name is hardcoded in it.

1. Copy [`plugins/dummy_attack/`](plugins/dummy_attack/) and change the slug in `pack.yaml`.
2. Implement the five methods of
   [`BaseAttack`](src/ragstrike/plugins/base/attack.py): `metadata`, `payloads`, `execute`,
   `analyze`, `recommendation`.
3. Drop the directory into `plugins/`. Run `ragstrike plugins` — it is there.

The split between `execute` and `analyze` is the part worth understanding. Sending a payload and
deciding whether it worked are different problems: one is I/O-bound and flaky, the other is a
judgment over recorded text. Keeping `analyze` pure is what will let Phase 5's replay harness re-run
analysis over stored evidence with no target contact — turning detector development into a fast
offline loop rather than a slow, nondeterministic one.

Discovery is manifest-first: `pack.yaml` is parsed and compatibility, capabilities, and declared
permissions are checked **before any plugin code is imported**. A plugin that fails any of those is
recorded with a reason and skipped, never fatal — and never silent. `ragstrike plugins` shows both
lists.

## Repository layout

| Path | Contents | v1.0.0 |
|---|---|---|
| [`docs/`](docs/) | The Software Design Document, four normative annexes, and 45 documents | ✅ |
| [`src/ragstrike/models/`](src/ragstrike/models/) | Domain entities, value objects, state enums | ✅ |
| [`src/ragstrike/core/`](src/ragstrike/core/) | Ports, configuration, errors, and the `ScanEngine` | ✅ |
| [`src/ragstrike/scheduler/`](src/ragstrike/scheduler/) | `ScanScheduler` — plans, then runs | ✅ |
| [`src/ragstrike/plugins/`](src/ragstrike/plugins/) | `BaseAttack`, discovery, registry | ✅ |
| [`src/ragstrike/target_adapters/`](src/ragstrike/target_adapters/) | `BaseTarget` + `FastAPIAdapter` | ✅ |
| [`src/ragstrike/database/`](src/ragstrike/database/) | aiosqlite, repositories, migrations | ✅ |
| [`src/ragstrike/logging/`](src/ragstrike/logging/) | Loguru behind the stdlib logging API | ✅ |
| [`src/ragstrike/cli/`](src/ragstrike/cli/) | Typer commands, Rich output, exit codes | ✅ |
| [`src/ragstrike/analyzers/`](src/ragstrike/analyzers/) · [`reporters/`](src/ragstrike/reporters/) | Detectors, scoring, reports | ✅ |
| [`src/ragstrike/attacks/`](src/ragstrike/attacks/) | Three attack packs; nine more declared, not built | ⚠️ |
| [`src/ragstrike/dashboard/`](src/ragstrike/dashboard/) | Streamlit UI — an HTTP client, never an importer | ✅ |
| [`src/ragstrike/api/`](src/ragstrike/api/) | `/api/v1` — **routing only, no handlers** | ❌ |
| [`plugins/`](plugins/) | Drop-in directory — the five evaluation packs and `dummy-attack` | ✅ |
| [`packs/`](packs/) | Also scanned, per Annex A naming | ✅ |
| [`configs/`](configs/) | `config.yaml`, `targets.yaml`, `logging.yaml`, analyzer and reporting | ✅ |
| [`validation/`](validation/) | Benchmarks, consistency checks, performance, the audit | ✅ |
| [`examples/`](examples/) | Eight worked examples, including real generated reports | ✅ |
| [`website/`](website/) | Site source. Not deployed | ✅ |
| [`tests/`](tests/) | 1,327 tests at 89.9% coverage | ✅ |

Start with [`ARCHITECTURE.md`](ARCHITECTURE.md) for the layer map and the dependency rule.

## Documentation

| Document | Read it for |
|---|---|
| [`docs/SDD.md`](docs/SDD.md) | The complete design — the single source of truth |
| [`docs/annex-a-directory-structures.md`](docs/annex-a-directory-structures.md) | Full directory trees and per-folder responsibilities |
| [`docs/annex-b-attack-catalog.md`](docs/annex-b-attack-catalog.md) | All twelve attack packs, with OWASP/ATLAS/CWE mapping |
| [`docs/annex-c-adrs.md`](docs/annex-c-adrs.md) | **Twenty-four** architecture decisions, with the alternatives that were rejected and why |
| [`docs/annex-d-risk-roadmap.md`](docs/annex-d-risk-roadmap.md) | Risk register, milestones, roadmap |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Layer map, dependency rule, how the scaffold maps to the SDD |
| [`INSTALL.md`](INSTALL.md) | Getting a development environment running |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Workflow, standards, how to contribute an attack pack |
| [`SECURITY.md`](SECURITY.md) | Responsible use, the plugin trust model, vulnerability reporting |
| [`ROADMAP.md`](ROADMAP.md) | Phases 1–11 and beyond |
| [`docs/limitations.md`](docs/limitations.md) | **What this does not do.** The most important document here |
| [`docs/project-metrics.md`](docs/project-metrics.md) | Every measured number, with its command |
| [`docs/technical-debt.md`](docs/technical-debt.md) | What is owed, what it costs, why it is unpaid |
| [`docs/known-issues.md`](docs/known-issues.md) | Symptoms, causes, workarounds |
| [`docs/architecture-index.md`](docs/architecture-index.md) | Which document answers which architectural question |
| [`docs/api-index.md`](docs/api-index.md) | The three surfaces, and which two answer |
| [`docs/plugin-index.md`](docs/plugin-index.md) | Every pack, built and unbuilt |
| [`docs/versioning-policy.md`](docs/versioning-policy.md) | Semver, compatibility, deprecation |
| [`docs/license-review.md`](docs/license-review.md) | Dependency licences, measured |
| [`docs/presentation/`](docs/presentation/) | Pitch, summaries, talk outline, demo script |
| [`examples/`](examples/) | Worked examples and real generated reports |

## Responsible use

RAGStrike is offensive tooling, and its defaults reflect that.

- **A scan cannot start without a stored authorization record** — who authorized it, and against what
  reference. It is a persisted field, not a checkbox, and it is embedded in every report.
- **The shipped configuration can only reach `localhost`.** Targeting a remote host requires an
  explicit configuration change plus an allowlist entry. Accidentally scanning a third party should
  require deliberate effort.
- **The rate limiter cannot be disabled.** A tool that can be trivially turned into a
  denial-of-service instrument against endpoints where every request has real cost is irresponsible.
- **Payloads are non-destructive by contract**, and every artifact written into a target is tracked
  and cleaned up. Residuals are reported prominently.

Use it on systems you own or are authorized to test. Nothing else.

## Licence

[Apache License 2.0](LICENSE).

---

<div align="center">
<sub>v1.0.0 · <a href="docs/limitations.md">Limitations</a> · <a href="ROADMAP.md">Roadmap</a> · <a href="docs/SDD.md">Design Document</a></sub>
</div>
