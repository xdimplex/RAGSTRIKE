# Architecture

> This document is the **navigational** view of the architecture: where things live, which layer they
> belong to, and what may import what. The **authoritative** design — with justification for every
> decision — is [`docs/SDD.md`](docs/SDD.md) and its four annexes. Where the two disagree, the SDD
> wins.

---

## 1. The one rule

**Dependencies point inward. Nothing else.**

```
Layer 4  Interface        api/  ·  cli/  ·  dashboard/
              ↓
Layer 3  Infrastructure   target_adapters/  ·  database/  ·  logging/
              ↓
Layer 2  Application      core/  ·  scheduler/  ·  analyzers/  ·  scoring
                          recommendations/  ·  reporters/  ·  plugins/
              ↓
Layer 1  Domain           models/  ·  core/contracts/
              ↓
Layer 0  Pure helpers     utils/
```

An inner layer may never import an outer one. `models/` imports nothing but the standard library.
`core/` never imports `database/` — it declares a repository *protocol* and receives an
implementation at the composition root.

This is not a convention that reviewers are asked to remember. It is enforced by
[`.importlinter`](.importlinter) as a CI gate, and it was wired up in Phase 1 — before there was any
code to violate it. Layering that is documented but unenforced degrades within months.

### The contracts that are checked

| # | Contract |
|---|---|
| 1 | `models` imports nothing from `ragstrike.*` — stdlib and `typing` only |
| 2 | `core`, `scheduler`, `analyzers`, `recommendations`, `plugins` never import `target_adapters`, `database`, `api`, `cli`, or `dashboard` |
| 3 | `dashboard` never imports any engine package — it is an HTTP client of the API and nothing else |
| 4 | `core.scoring` never imports anything that can call a model |
| 5 | `utils` imports nothing but the standard library |

**Contract 4 deserves a note.** It is the machine-checkable form of the promise "scores are never
produced by a model." A promise in a document degrades; an import-linter contract does not.

**Contract 3 deserves one too.** Streamlit re-runs its entire script on every widget interaction, so
engine state held in that process is either lost or duplicated. Forcing the dashboard through the API
also proves the API is complete — the reference UI cannot cheat — and keeps the UI replaceable.

---

## 2. Where everything lives

| Package | Layer | Owns | Never |
|---|---|---|---|
| [`models/`](src/ragstrike/models/) | 1 | Entities, value objects, state machines | Persistence, Pydantic, any outward import |
| [`core/contracts/`](src/ragstrike/core/contracts/) | 1 | Every port: adapter, plugin, detector, repository, renderer | Implementations |
| [`core/config/`](src/ragstrike/core/config/) | 2 | Layered config load, merge, fail-fast validation | Being read outside the composition root |
| [`core/executor/`](src/ragstrike/core/executor/) | 2 | Driving cases: concurrency, rate limit, retries, cancellation | Interpreting responses |
| [`core/evidence/`](src/ragstrike/core/evidence/) | 2 | Immutable probes, canary minting, cleanup, redaction | Judging anything |
| [`core/scoring/`](src/ragstrike/core/scoring/) | 2 | The versioned risk arithmetic | I/O, LLM calls, randomness |
| [`core/orchestrator/`](src/ragstrike/core/orchestrator/) | 2 | `run_scan` — the single use case | Computing what components compute |
| [`scheduler/`](src/ragstrike/scheduler/) | 2 | Deciding *what* to run | Any I/O at all |
| [`analyzers/`](src/ragstrike/analyzers/) | 2 | Judging responses via the detector ensemble | Transport or storage knowledge |
| [`recommendations/`](src/ragstrike/recommendations/) | 2 | Catalog lookup and effort-weighted prioritization | Generating advice at runtime |
| [`reporters/`](src/ragstrike/reporters/) | 2/3 | Report model + HTML/JSON/PDF renderers | Computing scores |
| [`plugins/`](src/ragstrike/plugins/) | 2/3 | Discovery, compatibility, activation | A hardcoded list of known packs |
| [`attacks/`](src/ragstrike/attacks/) | plugin | The twelve first-party packs | Being special-cased by the engine |
| [`target_adapters/`](src/ragstrike/target_adapters/) | 3 | Everything that knows what a target *is* | Attack or detection logic |
| [`database/`](src/ragstrike/database/) | 3 | aiosqlite repositories and migrations | Embeddings; leaking rows outward |
| [`logging/`](src/ragstrike/logging/) | 3 | structlog config and the redaction processor | Logging a raw secret |
| [`api/`](src/ragstrike/api/) | 4 | REST surface **and the composition root** | Business logic |
| [`cli/`](src/ragstrike/cli/) | 4 | Commands and exit codes | Logic the API lacks |
| [`dashboard/`](src/ragstrike/dashboard/) | 4 | Streamlit pages | Importing the engine |
| [`sdk/`](src/ragstrike/sdk/) | cross | Pack author tooling, test doubles, replay harness | Being a runtime dependency of the core |
| [`utils/`](src/ragstrike/utils/) | 0 | Pure, generic, stateless helpers | Anything domain-specific |

Every one of those directories has its own `README.md` with purpose, responsibilities, the files that
will land there, and an explicit list of what it must never contain.

---

## 3. Two naming collisions, resolved

These are the two places a new contributor reliably puts a file in the wrong directory.

**`models/` vs `database/models/`**

| | `src/ragstrike/models/` | `src/ragstrike/database/models/` |
|---|---|---|
| Holds | Domain entities and value objects | Table definitions and row shapes |
| Knows about | Business invariants | Columns, indices, constraints |
| Knows nothing about | Storage, serialization, transport | Business rules |
| Layer | 1 | 3 |

`database/mappers.py` is the only module that knows both shapes. Keeping them separate is what lets
the schema evolve without dragging the domain along.

**`logging/` vs `logs/`**

`src/ragstrike/logging/` is the structlog configuration package. `logs/` is the runtime output
directory (gitignored) holding four streams: `application/`, `scans/`, `errors/`, `debug/`.

The package name shadows the standard library within this distribution. Absolute imports are
mandatory project-wide and enforced by ruff, so `import logging` still resolves to the stdlib;
`ragstrike.logging` is always the full path here.

---

## 4. How the scaffold maps to the SDD

[Annex A](docs/annex-a-directory-structures.md) nests the application components under
`core/` (`core/scheduler/`, `core/analyzer/`, `core/reporting/`, `infrastructure/plugins/`, and so
on). Phase 1 promotes several of them to top-level packages — `scheduler/`, `analyzers/`,
`recommendations/`, `reporters/`, `plugins/`, `target_adapters/`, `models/`, `logging/`, `utils/`.

| Annex A path | This repository |
|---|---|
| `core/domain/` | `models/` |
| `core/scheduler/` | `scheduler/` |
| `core/analyzer/` | `analyzers/` |
| `core/recommendations/` | `recommendations/` |
| `core/reporting/` + `infrastructure/renderers/` | `reporters/` |
| `core/registry/` + `infrastructure/plugins/` | `plugins/` (`registry/` + `loader/` + `base/`) |
| `infrastructure/targets/` | `target_adapters/` |
| `infrastructure/database/` | `database/` |

**This is a packaging change, not an architectural one.** Every component keeps its layer, its
responsibilities, and its boundaries; the same five import-linter contracts enforce the same
dependency rule over the flatter tree. The flatter layout makes each subsystem discoverable at a
glance from the repository root, which matters for a project whose main extension points —
`plugins/`, `target_adapters/`, `attacks/` — are things contributors go looking for.

Recorded here because the SDD is the source of truth and deviations belong in writing rather than in
someone's memory.

---

## 5. What happens during a scan

```
User / CI
   │
   ▼
api/ or cli/ ──────────► core/orchestrator      ← the only entry point
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        plugins/registry  target_adapters  core/config
        (what exists)     (capabilities)   (how to behave)
              │               │
              └───────┬───────┘
                      ▼
                 scheduler/            pure: builds an immutable ScanPlan
                      │
                      ▼
                core/executor          I/O: concurrency, rate limit, retries
                      │
                      ▼
                core/evidence          immutable Probe records
                      │
                      ▼
                 analyzers/            detector ensemble → Verdicts
                      │
                      ▼
                core/scoring           pure arithmetic → Findings, grade
                      │
                      ▼
              recommendations/         catalog lookup, effort-weighted
                      │
                      ▼
                 reporters/            ReportModel → HTML / JSON
```

Each stage hands the next a value and knows nothing about how it is produced. The scheduler decides
*what*; the executor performs; the analyzer judges; the scorer computes; the reporter presents. None
of the four knows how another works.

Full sequence diagrams — including the indirect prompt injection flow and plugin discovery — are in
[SDD §25](docs/SDD.md).

---

## 6. The extension points

Three seams exist so that the common extensions never require a core change:

| To add | Do this | Core changes |
|---|---|---|
| An attack technique | Drop a pack in `packs/` or `pip install` one | **Zero** |
| A target type | Implement `TargetAdapter` in `target_adapters/` | **Zero** |
| A report format | Register a `Renderer` | **Zero** |

The first is verified by a CI test that installs a fixture pack and asserts it was discovered,
scheduled, and executed with no edits under `core/`. The first-party packs in `attacks/` register
through the same public entry-point mechanism third parties use — so if the extension path breaks,
the shipped product breaks first.

---

## 7. Where to start reading

1. [`docs/SDD.md`](docs/SDD.md) §§1–13 — problem, principles, layering, plugin architecture
2. [`docs/annex-c-adrs.md`](docs/annex-c-adrs.md) — the twenty decisions and their rejected alternatives
3. Any package README under [`src/ragstrike/`](src/ragstrike/) — each states its own boundaries
4. [`docs/annex-b-attack-catalog.md`](docs/annex-b-attack-catalog.md) — what the framework actually tests
