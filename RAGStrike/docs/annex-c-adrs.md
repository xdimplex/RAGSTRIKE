# Annex C — Architecture Decision Records

*Normative annex to [RAGSTRIKE-SDD-001](SDD.md). Version 1.0.0.*

Each ADR records a decision that constrains implementation. **Any deviation in Phases 1–10 requires a superseding ADR appended to this annex**, not an undocumented change. ADRs are immutable once accepted; they are superseded, never edited.

Status values: `Accepted` · `Superseded by ADR-NNN` · `Deprecated`.

---

## ADR-001 — Clean Architecture with an Enforced Dependency Rule

**Status:** Accepted · **Date:** 2026-07-29

**Context.** The mandated stack fixes five technologies (Streamlit, FastAPI, SQLite, ChromaDB, Ollama). All five have plausible replacements within the project's intended lifetime. The project must remain maintainable for years (G7).

**Decision.** Four layers — Domain, Application, Infrastructure, Interface — with dependencies pointing inward only. The rule is enforced by an import-linter contract in CI, not by convention.

**Alternatives considered.**
- *Flat package layout.* Faster initially; produces a codebase where replacing SQLite touches every module. Rejected.
- *Hexagonal without CI enforcement.* Layering that is documented but unenforced degrades within months as deadlines bite. Rejected — enforcement is the decision, not the diagram.

**Consequences.** More indirection up front. Contributors must learn where things go (mitigated by Annex A). Technology swaps become contained. Domain logic is testable with no infrastructure at all, which is what keeps unit tests under 30 seconds.

---

## ADR-002 — Plugin Discovery via Python Entry Points plus Local Directories

**Status:** Accepted · **Date:** 2026-07-29

**Context.** G4/NFR-01 require that third parties install attack packs with zero core modification.

**Decision.** Discovery through the `ragstrike.attack_packs` entry-point group (for pip-installed packs) *and* configured local directories (for development and private packs). First-party packs register through the identical public mechanism.

**Alternatives considered.**
- *Directory scan only.* Requires users to place files in a specific path; breaks pip distribution; no dependency resolution. Rejected as the sole mechanism, retained as a supplement.
- *Explicit registration in a core config file.* Every new pack becomes a core edit. Directly violates the Open/Closed Principle. Rejected.
- *Import-time auto-registration by scanning `sys.modules`.* Implicit, order-dependent, and unauditable. Rejected under the explicit-over-implicit principle.

**Consequences.** Packs are ordinary Python distributions with ordinary dependency resolution. Because first-party packs use the same path, the extension mechanism cannot silently rot — if it breaks, the shipped product breaks (SC2).

---

## ADR-003 — Manifest-First Plugin Metadata

**Status:** Accepted · **Date:** 2026-07-29

**Context.** The registry must decide whether a pack is compatible and what permissions it requests *before* granting it code execution.

**Decision.** Every pack ships a declarative `pack.yaml` parsed without importing pack code. Python modules are imported lazily and only when a declared custom detector is actually needed.

**Alternatives considered.**
- *Metadata as Python class attributes.* Requires importing untrusted code to read metadata — inverting the safety ordering. Also makes listing 40 installed packs an expensive operation. Rejected.
- *Metadata in `pyproject.toml`.* Would work for pip-installed packs, not for directory-based development packs, and cannot carry the nested attack/payload/detector structure cleanly. Rejected.

**Consequences.** Manifests are lintable in CI without a Python environment. Pack listing is fast. Compatibility and permission checks happen before execution. Cost: a schema to maintain and version.

---

## ADR-004 — Separate Attack Generation from Result Detection

**Status:** Accepted · **Date:** 2026-07-29

**Context.** Generating a payload and deciding whether it worked are different problems with different failure modes and different iteration speeds.

**Decision.** `Attack` (what to send) and `Detector` (how to judge) are separate abstractions bound declaratively with weights in the attack definition.

**Alternatives considered.**
- *Attack owns its own success check.* Simple, and it is what most red-team scripts do. It produces N duplicated detection implementations, makes ensemble judgment impossible, and makes detector improvement require touching every attack. Rejected.

**Consequences.** N attacks reuse M detectors. Detector quality improves globally with one change. Ensemble aggregation (ADR-006) becomes possible. Enables the replay harness (ADR-012). Cost: an extra binding layer in the attack schema.

---

## ADR-005 — Canary Tokens as the Primary Oracle

**Status:** Accepted · **Date:** 2026-07-29

**Context.** The oracle problem — deciding automatically whether an attack on a natural-language system succeeded — is the hardest correctness problem in the project. Heuristic text matching produces both false positives and false negatives at rates that would make the tool untrustworthy.

**Decision.** Wherever the test design permits, plant a unique high-entropy token and define success as its appearance where it must not appear. Canary detection is the primary signal; everything else corroborates.

**Alternatives considered.**
- *Regex heuristics as primary.* Brittle against paraphrase, language, and formatting variation. Retained as a supporting signal only.
- *LLM judge as primary.* Nondeterministic, model-version-dependent, unarguable in a disputed report. Rejected as primary — see ADR-006.

**Consequences.** Near-zero false-positive rate where canaries apply; language- and model-independent. Requires a cleanup obligation for any canary written into a target corpus, tracked in the `canaries` table with residuals surfaced in reports. Some attacks (hallucination, subtle policy violation) admit no canary and fall back to weaker evidence with correspondingly lower reported confidence — which is the honest outcome.

---

## ADR-006 — Weighted Noisy-OR Signal Aggregation with a Capped LLM Judge

**Status:** Accepted · **Date:** 2026-07-29

**Context.** Multiple weak, independent signals should combine into strong evidence; but a nondeterministic judge must never be able to single-handedly produce a confident finding (SC4, SC5).

**Decision.** Default aggregation is weighted noisy-OR over fired signals, with evidence-span deduplication before combination. The LLM judge detector is off by default in the standard profile, may never be the sole detector for a first-party attack, contributes at most 0.7 confidence, runs at temperature 0 with forced structured output, and every finding depending on it is labelled *model-assisted* in reports.

**Alternatives considered.**
- *Maximum of signals.* Cannot express that two independent weak indicators are stronger than either alone. Rejected as default; available per-attack.
- *Weighted mean.* Dilutes a single strong deterministic signal with weak ones. Rejected as default.
- *Unconstrained LLM judge.* Simplest to implement, best semantic coverage, and fatal to reproducibility, trend comparison, and defensibility. Rejected.

**Consequences.** Confidence is bounded, monotonic, and interpretable. Scores do not move when someone upgrades a model. The judge earns its place on genuinely semantic questions and is fenced elsewhere. Cost: correlated detectors require span deduplication to avoid double counting.

---

## ADR-007 — Repository Pattern over Raw aiosqlite, No ORM

**Status:** Accepted · **Date:** 2026-07-29

**Context.** The stack mandates aiosqlite. The schema is small, stable, and accessed through well-known paths.

**Decision.** Repository interfaces in the domain layer; aiosqlite implementations in infrastructure; parameterized raw SQL; numbered, checksum-verified, forward-only migrations. The probe repository exposes **no update or delete method**, making evidence immutability a type-level guarantee rather than a rule people remember.

**Alternatives considered.**
- *SQLAlchemy ORM.* Heavyweight dependency, an object-identity model this domain does not need, and query obscurity in a system whose queries must be reviewable. Rejected.
- *SQLAlchemy Core only.* Closer, but still a large dependency for expression-building this schema does not need. Rejected; noted as the escape hatch if multi-backend support is ever required.
- *Direct aiosqlite calls with no repository layer.* Removes the seam that makes persistence swappable and makes the domain untestable without a database. Rejected.

**Consequences.** Minimal dependency footprint (NFR-02). Queries are explicit and reviewable. Migration checksum mismatch is a fail-fast startup error, because running against an unexpected schema corrupts history silently.

---

## ADR-008 — A Single Abstract Target Interface with Capability Negotiation

**Status:** Accepted · **Date:** 2026-07-29

**Context.** G3 requires that the attack engine never know which provider is underneath. But targets genuinely differ: some accept document ingestion, some expose retrieved chunks, some are stateless.

**Decision.** One `TargetAdapter` port with a small mandatory surface, plus narrow capability protocols (`SupportsChat`, `SupportsIngest`, `SupportsRetrievalIntrospection`, …). Attacks declare `requires_capabilities`; the scheduler filters and records every exclusion as an explicit coverage gap.

**Alternatives considered.**
- *One fat interface with optional methods raising `NotImplementedError`.* Violates Interface Segregation; makes capability discovery a matter of catching exceptions at runtime, after a case has already been scheduled. Rejected.
- *Per-provider engine branches.* Directly violates G3. Rejected.

**Consequences.** Adapters are substitutable and the SDK's adapter conformance suite makes that machine-verified (Liskov). Coverage becomes a first-class reported quantity, because a scan that could only run 40% of its cases must never render identically to one that ran 100%.

---

## ADR-009 — VulnerableRAG and SecureRAG Share One Repository and One Codebase

**Status:** Accepted · **Date:** 2026-07-29

**Context.** The requirement is explicit: same functionality, same UI, same PDFs, same model — differing only in defensive controls. SC1 depends on the difference between them being *exactly* the security controls.

**Decision.** One repository with `packages/ragcore/` shared and two thin profiles (`apps/vulnerable/`, `apps/secure/`) differing only in the composition of a `SecurityPolicy` chain. The vulnerable profile constructs an **empty chain in code**, not via a configuration flag. A functional-parity test asserts both profiles answer benign queries equivalently.

**Alternatives considered.**
- *Two independent repositories.* Matches the literal wording of the brief. They will drift — a UI change lands in one, a chunker is tuned in the other — and once they drift, the differential test stops measuring security and starts measuring incidental difference, while continuing to look correct. Rejected. If separate published repositories are later wanted for pedagogy, they can be generated from this monorepo by a release job.
- *One app with a `secure: true` config flag.* A single misconfiguration silently hardens the vulnerable target and invalidates every scan result with no visible symptom. Rejected — the separation must be structural.

**Consequences.** The diff between the two profiles is an executable remediation guide and the project's best teaching artifact. Deviates from the literal "another repository" wording; the deviation is deliberate and recorded here.

---

## ADR-010 — The Dashboard Is an HTTP Client of the API, Never an Importer of the Core

**Status:** Accepted · **Date:** 2026-07-29

**Context.** Streamlit re-runs its entire script on every widget interaction. Engine state held in that process is lost or duplicated.

**Decision.** `dashboard/` may import only its own modules and an HTTP client. Importing `core.*` or `infrastructure.*` is an import-linter contract violation that fails CI.

**Alternatives considered.**
- *Streamlit imports the engine directly.* Fewer moving parts for a single-user local install, and it makes long-running scans structurally impossible to manage, guarantees the API drifts behind the UI, and welds the engine to a UI framework. Rejected.

**Consequences.** The API is provably complete, because the reference UI cannot cheat. CLI and CI reach exactly the same surface. The dashboard is replaceable. The engine can run on a different machine. Cost: local development requires two processes (handled by a compose file and a bootstrap script).

---

## ADR-011 — Deterministic, Versioned, Hand-Reproducible Risk Scoring

**Status:** Accepted · **Date:** 2026-07-29

**Context.** Scores drive remediation budgets and sometimes go-live decisions. A target that has not changed must not change grade because RAGStrike was upgraded.

**Decision.** `F = 10 · I · E · C` per finding; two-stage aggregation (per-category maximum, then weighted noisy-OR across categories, then a bounded density adjustment); published weight tables under a `scoring_model_version`; the full arithmetic reproduced in the report's Risk Analysis section. Trend views refuse cross-version comparison without an explicit recompute.

**Alternatives considered.**
- *Mean of finding scores.* One hundred INFO findings dilute a CRITICAL. Rejected.
- *Plain noisy-OR over every finding.* Saturates to 100 as soon as a handful of medium findings appear, and rewards packs that ship more payloads. Rejected — hence the per-category maximum in stage 1.
- *Full CVSS vector adaptation.* Familiar to security teams, but its base metrics (attack vector, privileges required, user interaction) map poorly onto LLM application weaknesses and would encode false precision. Rejected; OWASP/CWE mapping provides the interoperability CVSS would have.

**Consequences.** Any reader can verify a score by hand from the report. Exploitability (`successes/attempts`) is measured, not assumed — the term most scanners omit and are most misleading without. Weight changes require a version bump and a changelog entry.

---

## ADR-012 — Immutable Evidence and an Offline Replay Harness

**Status:** Accepted · **Date:** 2026-07-29

**Context.** Detector quality determines whether the tool is right. Iterating detectors against a live LLM is slow, costly, and nondeterministic.

**Decision.** Probes are immutable records of every request/response exchange. The analyzer is a pure function of `(evidence, detector config)`. A replay harness re-runs analysis over stored evidence with no target contact, and a committed golden evidence corpus provides byte-stable regression tests.

**Alternatives considered.**
- *Analyze inline and discard raw responses.* Saves storage; makes detector iteration require re-running scans, makes regression testing impossible, and makes findings unverifiable after the fact. Rejected.

**Consequences.** Detector development becomes a fast, offline, deterministic unit-test loop — the same insight that made packet-capture replay central to network IDS development. Storage grows, mitigated by the retention/compaction policy. Evidence may contain real secrets, requiring the redaction policy (ADR-013).

---

## ADR-013 — Redaction in the Pipeline, Not at Call Sites

**Status:** Accepted · **Date:** 2026-07-29

**Context.** Evidence and logs contain, by design, whatever the target leaked — potentially real credentials and real personal data.

**Decision.** Redaction is a processor in the structlog pipeline and a stage in the report renderer, applied centrally. Raw evidence exists only in the local database. Exported artifacts default to `partial` redaction (masked spans, preserved context); `none` requires an explicit operator choice recorded on the report.

**Alternatives considered.**
- *Redact at each logging call site.* One forgotten call leaks. Unauditable. Rejected.
- *Never store raw responses.* Destroys the replay harness and makes findings unverifiable. Rejected.

**Consequences.** No future `log.info` can leak a canary or a matched secret. Reports are shareable by default. `data/` and `reports/` are gitignored in both repositories.

---

## ADR-014 — Server-Sent Events for Progress Streaming

**Status:** Accepted · **Date:** 2026-07-29

**Context.** Scans run for minutes; the dashboard must show live progress.

**Decision.** SSE at `GET /api/v1/scans/{id}/events`, with monotonic sequence numbers for gap detection and resumption.

**Alternatives considered.**
- *WebSockets.* Adds bidirectional protocol handling, connection state, and heartbeats for a flow with no client-to-server channel. Rejected.
- *Client polling only.* Simplest; poor responsiveness and wasteful at scale. Retained as the Streamlit fallback, rejected as the primary.

**Consequences.** Plain HTTP, automatic browser reconnection, trivial FastAPI implementation, graceful degradation to polling.

---

## ADR-015 — Plugin API Versioned Independently of the Application

**Status:** Accepted · **Date:** 2026-07-29

**Context.** An ecosystem in which every core release breaks every third-party pack has no third-party packs.

**Decision.** A `PLUGIN_API_VERSION` separate from the application version. Packs declare a compatible SemVer range in `pack.yaml`. MAJOR = breaking contract change; MINOR = additive; PATCH = clarification. The core ships a compatibility matrix and, for one MAJOR cycle, a shim translating the previous schema version. Incompatible packs are refused with a clear message and recorded as a coverage gap — never crash-loaded, never silently ignored.

**Alternatives considered.**
- *Single version for app and plugin API.* Every patch release signals a potential break; pack authors cannot reason about compatibility. Rejected.
- *No versioning.* Silent breakage at upgrade time. Rejected.

**Consequences.** Pack authors have a stable contract. Core can evolve internals freely. Cost: a compatibility matrix and a shim layer to maintain across MAJOR transitions.

---

## ADR-016 — Payloads Are Data, Rendered by a Non-Evaluating Template Engine

**Status:** Accepted · **Date:** 2026-07-29

**Context.** Payload packs will be contributed by security researchers, many of whom are not Python developers (FR-20).

**Decision.** Payloads are YAML templates with variable bindings, rendered by a restricted engine with no expression evaluation, no attribute traversal, no imports, and no filters beyond a fixed safe set.

**Alternatives considered.**
- *Payloads as Python callables.* Maximum flexibility; makes installing a payload pack equivalent to executing untrusted code and excludes non-programmer contributors. Rejected.
- *Full Jinja2 with sandboxing.* Sandbox escapes in templating engines are a recurring class of vulnerability. Rejected in favour of an engine that has no evaluation capability to escape from.

**Consequences.** Payload contribution is accessible. The scanner's own attack surface stays small. Payload-set files can be validated, diffed, and licensed independently. Cost: genuinely dynamic payload generation requires a mutator (code), which is a deliberate and reviewed extension point.

---

## ADR-017 — Mandatory Authorization Gate and Loopback-Default Targeting

**Status:** Accepted · **Date:** 2026-07-29

**Context.** RAGStrike is offensive tooling. Its default configuration determines what happens when someone uses it carelessly.

**Decision.** No scan starts without a stored authorization record (`authorized_by`, `authorization_ref`, timestamp), embedded in every report. The shipped configuration allows only `localhost`/`127.0.0.1`/`::1`; remote targets require an explicit configuration change plus an allowlist entry. The token-bucket rate limiter cannot be disabled. RAGStrike will not implement WAF-evasion, rate-limit evasion, or detection-avoidance features.

**Alternatives considered.**
- *Authorization as an unchecked UI checkbox.* Provides no record and no accountability. Rejected — it must be a persisted field on the target, present in the report.
- *Permissive default targeting.* Every accidental scan of a third party is an incident. Rejected.

**Consequences.** Pointing RAGStrike at a remote system is a deliberate act with a paper trail. The tool cannot be trivially repurposed as a denial-of-service instrument against endpoints where every request has real cost. Minor friction for legitimate users, which is the correct trade for offensive tooling.

---

## ADR-018 — Single-Process Asyncio Execution

**Status:** Accepted · **Date:** 2026-07-29

**Context.** NFR-04 requires ~400 cases in 15 minutes against a local Ollama target. The bottleneck is the target's inference throughput, not RAGStrike.

**Decision.** One process, `asyncio.TaskGroup`, bounded semaphore, token-bucket rate limiter, thread-pool offload for CPU-bound rendering and similarity work.

**Alternatives considered.**
- *Celery/Redis worker fleet.* Adds a broker, deployment burden, serialization boundaries, and failure modes while relieving no actual constraint. Violates KISS. Rejected.
- *Multiprocessing.* The workload is I/O-bound; process parallelism buys nothing and complicates evidence writes. Rejected.

**Consequences.** Trivial local install and debugging. Evidence writes stay transactional in one connection. The orchestrator interface is the seam at which a queue-backed implementation could be introduced if fleet-scale scanning is ever required.

---

## ADR-019 — Recommendations Come from a Versioned Catalog, Never Runtime Generation

**Status:** Accepted · **Date:** 2026-07-29

**Context.** Remediation guidance appears in artifacts used for compliance and engineering planning.

**Decision.** A YAML catalog of peer-reviewed entries keyed by attack, category, and evidence traits. Runtime LLM generation of advice is prohibited. The remediation plan is prioritized by risk reduced per unit of effort, not by raw severity.

**Alternatives considered.**
- *LLM-generated remediation.* Adaptive and specific; also nondeterministic, unreviewable, occasionally wrong, and different for every user reading the same finding. Rejected.
- *Static text hardcoded in detector modules.* Untranslatable, unversionable, duplicated. Rejected.

**Consequences.** Guidance is reviewed once and cited. Improving the catalog improves every past scan on report regeneration. Effort-weighted prioritization surfaces the single prompt-template fix that closes six findings ahead of the architectural change that closes one.

---

## ADR-020 — Coverage Is a Reported First-Class Quantity

**Status:** Accepted · **Date:** 2026-07-29

**Context.** The most dangerous failure mode a scanner has is that a scan covering 40% of the surface and one covering 100% both render as "no findings."

**Decision.** Every skipped case records a reason. Every report contains a Coverage section. Every grade is reported with its coverage fraction, and grades derived from under 60% coverage carry an explicit partial-coverage qualifier. Every budget truncation is logged. Every incompatible plugin appears in Coverage. Every report contains a Methodology and Limitations section stating that absence of findings is not proof of security.

**Alternatives considered.**
- *Report only findings.* Cleaner reports; creates false assurance, which is worse than no scan. Rejected.

**Consequences.** Reports are longer and occasionally less flattering. Users can tell the difference between "secure" and "untested," which is the entire point.

---

## ADR-021 — The Dashboard Ships Against an Unimplemented API, Behind a Demo Transport

**Status:** Accepted · **Date:** 2026-07-29

**Context.** Phase 12 specified a Streamlit dashboard reading live data from `/api/v1`. On arriving at the phase, `/api/v1` turned out to be an empty scaffold — the API phase had produced routing and no handlers. Three options existed: implement the API inside Phase 12 (merging phases, forbidden); import the engine directly from the dashboard (contradicting ADR-010); or ship the client against the contract that does not answer yet.

**Decision.** Ship the client. All backend access goes through a `BackendTransport` Protocol with two implementations: `HttpTransport`, which speaks to `/api/v1` and reports `BACKEND OFFLINE` when it cannot; and `DemoTransport`, which serves fixtures through the same interface for demonstration and testing.

The demo transport's fixture plugin is named `reference-diagnostic` rather than any real pack slug, because a Phase 4 test asserts that no plugin name appears in framework code — and a fixture is not a reason to weaken that test.

**Alternatives considered.**
- *Import the engine directly.* Immediate live data; permanently couples the UI to internals and makes the layer contract unenforceable. Rejected — the coupling would never have been undone.
- *Silently fall back to demo data when the backend is down.* Rejected outright: a dashboard that shows plausible numbers without saying they are fictional is worse than one that shows nothing.

**Consequences.** The dashboard is complete and cannot show live results until the API is implemented. The offline state is loud and unmistakable. When handlers land, no dashboard code changes.

---

## ADR-022 — SecureRAG Is a Standalone Repository, with a Machine-Checked Compatibility Suite

**Status:** Accepted · **Date:** 2026-07-29 · **Amends:** ADR-009

**Context.** ADR-009 decided that VulnerableRAG and SecureRAG share one repository and one codebase, because two repositories drift. The Phase 13 brief specified a standalone `D:\Project\SecureRAG`. The conflict was raised explicitly and the standalone layout was chosen by the project owner.

**Decision.** SecureRAG is an independent repository. ADR-009's *reasoning* is not withdrawn — the drift risk is real, and it is now mitigated by a machine check instead of by shared code: `tests/parity/test_compatibility.py` reads `/openapi.json` from both applications and fails if the surfaces diverge.

That test replaced an earlier version that walked `client.app.routes`, silently returned an empty set, and could therefore never fail. **A compatibility test that cannot fail is worse than none**, because it converts an open question into false assurance.

**Alternatives considered.**
- *Keep the shared codebase and decline the brief.* Rejected: the layout is the owner's call, not the architecture's.
- *Take the standalone layout without a parity check.* Rejected: that accepts ADR-009's cost without buying anything back.

**Consequences.** Drift is caught at test time rather than prevented by construction — strictly weaker, and honestly so. Each lab application can now evolve its internals freely, which the hardened prompt builder made immediate use of.

---

## ADR-023 — An Unrun Comparison Reports NOT_RUN, Never a Mismatch

**Status:** Accepted · **Date:** 2026-07-30

**Context.** The validation runner compares each benchmark's outcome on VulnerableRAG against its outcome on SecureRAG. The first implementation derived comparison status purely from whether the two outcomes matched. A benchmark whose plugin had been disabled therefore compared `NOT_RUN` against `NOT_RUN` — and, on some paths, an unrun target against a run one — producing **MISMATCH**.

That turns "you disabled some plugins" into "the scanner is broken", in the one document whose entire job is to say whether the scanner works.

**Decision.** `NOT_RUN` on either side short-circuits: the comparison reports `NOT_RUN`, and the summary counts it separately from both agreements and mismatches. Benchmarks live in `datasets/*.yaml` as data, never in Python, for the same reason payloads do (ADR-016).

**Alternatives considered.**
- *Exclude unrun benchmarks from the summary.* Rejected — it makes coverage invisible, which ADR-020 exists to prevent.

**Consequences.** The summary distinguishes three states rather than two. A partial validation run reads as partial.

---

## ADR-024 — v1.0.0 Ships with Known Debt Recorded, Not Suppressed

**Status:** Accepted · **Date:** 2026-07-30

**Context.** The pre-release audit found eleven `mypy` errors in code written in Phases 3–5, six `bandit` findings, and 29 packages without a README. Every one could have been made to disappear: a blanket `# type: ignore`, a broad `nosec`, a stub README per directory.

**Decision.** Suppress nothing that is not demonstrably false. Each of the six bandit findings was individually established as a false positive and annotated **at the site**, with the reason, rather than silenced in a config file. The only project-wide skip is B105, because this framework's outcome vocabulary literally contains the word `PASS` and that will false-positive forever. The eleven mypy errors and the README gap are recorded in [`technical-debt.md`](technical-debt.md) with estimates, and named in the audit report and the release checklist.

The audit's cycle detector follows the same principle: it separates import-time cycles from deferred ones instead of reporting a count that looks better. Three iterations were needed to get there — 32 cycles, then 1, then the correct 0 — and the wrong answers are documented in the module.

**Alternatives considered.**
- *Fix everything first.* Rejected: the mypy fixes require editing Phases 3–5, which the phase discipline forbids.
- *Suppress and ship clean.* Rejected. A green board that was made green by suppression teaches maintainers to distrust the board.

**Consequences.** The audit report says "11 errors" where it could have said "clean". Anyone evaluating the repository can see exactly what is owed and what it would cost.

---

## C.1 Superseded and Deferred Decisions

| Topic | Status | Note |
|---|---|---|
| OS-level plugin sandboxing (subprocess isolation) | **Deferred** | Documented honestly in the plugin trust model: installing a pack grants the trust of installing a Python package. Roadmap item R-07 (Annex D). Declaring a sandbox that does not exist would be worse than declaring none. |
| PDF report rendering | **Deferred to Phase 11** | HTML and JSON are the v1 contract; the renderer registry makes PDF additive. |
| SARIF output | **Deferred** | Natural fit for CI integration; blocked on nothing but priority. |
| Multi-backend persistence (PostgreSQL) | **Deferred** | The repository interfaces are the seam. No current requirement. |
| Distributed/queued execution | **Deferred** | ADR-018 records the seam. No current requirement. |
| Agentic / tool-calling target support (LLM06) | **Deferred to v2** | Requires an action-side sandbox to test excessive agency without causing real side effects. |
