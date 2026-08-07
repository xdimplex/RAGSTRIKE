# Documentation

## The design

| Document | What it covers |
|---|---|
| **[SDD.md](SDD.md)** | The complete Software Design Document — **the single source of truth**. Sections 1–40: problem, requirements, layering, plugin architecture, analyzer, scoring, persistence, API, CLI, UI, safety, testing. |
| [Annex A](annex-a-directory-structures.md) | Complete directory trees for both repositories, with per-directory responsibilities |
| [Annex B](annex-b-attack-catalog.md) | All twelve attack packs: techniques, detectors, impact, OWASP/ATLAS/CWE mapping |
| [Annex C](annex-c-adrs.md) | **Twenty-four** Architecture Decision Records, each with the alternatives that were rejected and why |
| [Annex D](annex-d-risk-roadmap.md) | Risk register, phase milestones with exit criteria, post-v1 roadmap |

The annexes are **normative**. They are part of the SDD, not supplementary reading.

## Release documentation

Written in Phase 14. These are the documents a user, an administrator, or a maintainer reads.

| Document | For |
|---|---|
| [User guide](user-guide.md) | Running scans; reading a result |
| [Administrator guide](administrator-guide.md) | Configuration, safety policy, storage, logging |
| [Developer guide](developer-guide.md) | Extending the framework; the dependency rule |
| [Deployment guide](deployment-guide.md) | Install, the lab, CI, upgrading |
| [Demonstration](demo.md) | The repeatable end-to-end walkthrough |
| [Troubleshooting](troubleshooting.md) | Indexed by symptom |
| [FAQ](faq.md) | The questions worth answering plainly |
| [**Known limitations**](limitations.md) | **What this does not do. The most important document here** |
| [Validation results](validation-results.md) | What the differential run against the live lab actually showed |
| [Roadmap v2](roadmap-v2.md) | Roadmap items only; nothing implemented |
| [Release checklist](release-checklist.md) | Run in order before tagging |
| [Installation validation](installation-validation.md) | Clean-environment verification, step by step |
| [Dependency summary](dependency-summary.md) | Every dependency, and why |
| [Third-party attribution](third-party-attribution.md) | Licences and standards referenced |

## Release documentation (Phase 15)

Written for the v1.0.0 tag. These are the documents a maintainer, a reviewer, or a contributor reads.

| Document | For |
|---|---|
| [**Project metrics**](project-metrics.md) | Every measured number, with the command that produced it |
| [Audit report](audit-report.md) | Structure, cycles, dead code, and the tool results |
| [**Technical debt**](technical-debt.md) | What is owed, what it costs, why it is unpaid |
| [Known issues](known-issues.md) | Symptoms, causes, workarounds |
| [Maintenance guide](maintenance-guide.md) | What to run, what to watch, which invariants not to break |
| [Refactoring notes](refactoring-notes.md) | Changes made, and the ones deliberately not made |
| [Versioning policy](versioning-policy.md) | Semver, compatibility, deprecation |
| [Licence review](license-review.md) | Dependency licences, measured — supersedes the attribution page on licensing |

### Indexes

| Index | Answers |
|---|---|
| [Architecture index](architecture-index.md) | Which document answers which architectural question |
| [API reference index](api-index.md) | The three surfaces, and which two actually answer |
| [Plugin index](plugin-index.md) | Every pack — built, and declared but unbuilt |
| [Evaluation pack index](evaluation-pack-index.md) | The five evaluation packs and their coverage gaps |

### Plugin developer experience

| Document | For |
|---|---|
| [Plugin workflow](plugin-workflow.md) | Idea to shipped pack |
| [Plugin checklist](plugin-checklist.md) | Before you ship |
| [Plugin review checklist](plugin-review-checklist.md) | Before you approve someone else's |
| [Plugin testing guide](plugin-testing-guide.md) | How to test one so the tests mean something |

### Presentation

[`presentation/`](presentation/) — elevator pitch, recruiter summary, technical summary, talk outline,
demo script, architecture diagrams.

Website source is in [`../website/`](../website/); worked examples in [`../examples/`](../examples/).

## The subsystems

One guide per implemented subsystem. These describe what was built and why; the SDD describes what
was designed. Where they disagree, the guide records the divergence and its reason.

| Document | What it covers |
|---|---|
| [SDK guide](sdk-guide.md) | Writing an attack pack against the developer kit |
| [Plugin development](plugin-development.md) · [Plugin lifecycle](plugin-lifecycle.md) | The plugin contract and its nine-method lifecycle |
| [Evaluation plugins](evaluation-plugins.md) | The five non-offensive evaluation plugins |
| [Prompt injection](prompt-injection-pack.md) · [Prompt leakage](prompt-leakage-pack.md) · [Context poisoning](context-poisoning-pack.md) | The three shipped attack packs |
| [Analyzer engine](analyzer-engine.md) | How raw plugin results become standardized findings |
| [Reporting engine](reporting-engine.md) | One model, N renderers |
| [Dashboard](dashboard.md) | The Streamlit interface, and why it never imports the engine |

## Reading order

**New contributor:** [`../README.md`](../README.md) → [`../ARCHITECTURE.md`](../ARCHITECTURE.md) →
[`../CONTRIBUTING.md`](../CONTRIBUTING.md) → any folder README under `src/ragstrike/`.

**Implementing a phase:** SDD sections for your subsystem → the relevant ADRs → Annex A for where
files go → the folder README for boundaries.

**Writing an attack pack:** [Annex B](annex-b-attack-catalog.md) → SDD §13 (plugin architecture) →
SDD §14 (SDK) → [`../CONTRIBUTING.md`](../CONTRIBUTING.md#contributing-an-attack-pack).

**Reviewing a design decision:** [Annex C](annex-c-adrs.md). If a decision is not recorded there, it
has not been made.

## Amending the design

The SDD is the source of truth for every phase. Changing it requires a **superseding ADR** appended
to Annex C — never an edit to an existing one. ADRs are immutable once accepted, so that the
reasoning behind a past decision survives even after the decision is reversed.

## Planned (Phase 11)

`architecture/`, `guides/`, `reference/`, and `policy/` subdirectories per Annex A, published as a
MkDocs Material site.
