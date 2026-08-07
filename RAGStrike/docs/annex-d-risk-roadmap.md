# Annex D — Risk Register, Development Milestones, and Roadmap

*Normative annex to [RAGSTRIKE-SDD-001](SDD.md). Version 1.0.0.*

---

## D.1 Risk Register

Likelihood and impact are rated **L / M / H**. Exposure is the product, ranked. Every risk has a named trigger — the observable event that means the mitigation must be activated. A risk without a trigger is a wish.

### D.1.1 Critical Exposure (H × H)

**R-01 — The oracle is wrong: findings that are not real, or missed findings that are.**

*Category:* Correctness · *Likelihood:* H · *Impact:* H

A scanner that reports vulnerabilities that do not exist gets switched off; one that misses real vulnerabilities gets trusted and shouldn't be. This is the single risk that can make the entire project worthless while every test passes.

*Mitigation.* Canary-first oracle design (ADR-005) removes ambiguity wherever it can be planted. Ensemble aggregation (ADR-006) prevents any one weak signal from producing a confident finding. The confidence-capped judge cannot single-handedly create a HIGH. The differential test (SC1) is the ground-truth check, and it asserts **per-category minimum finding counts on VulnerableRAG**, so the "detects nothing, grades everything A" failure mode cannot pass. Every pack must additionally be validated against SecureRAG for false positives before merge.

*Trigger.* Any pack whose detection rate on VulnerableRAG drops below its declared minimum, or whose false-positive rate on SecureRAG exceeds zero, in any nightly run.

---

**R-02 — LLM nondeterminism makes results unreproducible and untrustworthy over time.**

*Category:* Correctness · *Likelihood:* H · *Impact:* H

The same payload succeeds on attempt three and fails on one, two, and four. A tool that reports a different grade on every run cannot be used for trend analysis or for gating a release.

*Mitigation.* Exploitability is **measured, not assumed**: every attack declares an attempt count and the score uses `successes/attempts` (§17.2 of the SDD). Seeded, deterministic scheduling. Judge at temperature 0 and off by default. Determinism test in CI (SC4). Scoring model versioned so a formula change is visible rather than silent.

*Trigger.* The determinism test failing, or variance in aggregate risk across repeated scans of the same target exceeding ±5 points.

---

**R-03 — Session contamination inflates results.**

*Category:* Correctness · *Likelihood:* M · *Impact:* H

If a jailbreak in case 12 persists into cases 13–400 on a stateful target, most subsequent cases "succeed" for the wrong reason and the report is worthless — while looking dramatic and convincing.

*Mitigation.* Fresh-session semantics are a mandatory adapter behaviour, not an optimization. Attacks default to `fresh_session: true`; the few that legitimately need continuity declare it explicitly and are capability-gated on `SESSION_MEMORY`. Adapter conformance suite tests that `reset_session` actually resets.

*Trigger.* A scan in which success rate rises monotonically with case index — an automatic check in the differential job.

---

### D.1.2 High Exposure

**R-04 — Plugin API churn breaks the third-party ecosystem.**

*Likelihood:* M · *Impact:* H · *Mitigation:* Independent Plugin API versioning (ADR-015), declared compatibility ranges, one-MAJOR-cycle shim layer, published compatibility matrix, first-party packs using the public path so breakage is felt internally first. *Trigger:* Any PR that changes a file under `core/contracts/` without a Plugin API version bump.

**R-05 — Scanning causes harm to a target (cost, outage, residual poison).**

*Likelihood:* M · *Impact:* H · *Mitigation:* Non-disableable rate limiter; loopback-default targeting with explicit allowlist (ADR-017); `cost-amplification` restricted to `deep` with an acknowledgement flag; mandatory cleanup of every ingested artifact with residuals surfaced in reports; no evasion features. *Trigger:* Any user report of unexpected target load, or any scan completing with `cleanup_state = RESIDUAL` entries.

**R-06 — Evidence containing real secrets or PII leaks through reports or logs.**

*Likelihood:* M · *Impact:* H · *Mitigation:* Redaction as a pipeline processor rather than a per-call-site responsibility (ADR-013); `partial` redaction default on all exports; `data/` and `reports/` gitignored in both repositories; gitleaks in CI. *Trigger:* Any finding of unredacted secret material in an exported artifact during review or CI secret scanning.

**R-07 — A malicious or careless third-party pack compromises the host.**

*Likelihood:* L · *Impact:* H · *Mitigation:* Manifest parsed before any import (ADR-003); declared permissions displayed at install time with loud warnings for elevated requests; conformance suite tests for undeclared network egress and filesystem writes; **the trust model is stated honestly in the docs** — installing a pack grants the trust of installing a Python package. OS-level sandboxing is a roadmap item (R-07 → v2), not a current claim. *Trigger:* Any pack requesting `network_egress: true` or `filesystem_write: true` entering the first-party recommended list.

**R-08 — VulnerableRAG is deployed somewhere reachable.**

*Likelihood:* M · *Impact:* H · *Mitigation:* Loopback-only binding by default; Compose publishes no external ports; refuses to start without `RAGSTRIKE_LAB_ACK=1`; prominent README and startup-banner warnings; `LAB_SAFETY.md`; never published as a PyPI package or a `:latest` public image. *Trigger:* Any issue, discussion, or telemetry indicating a non-loopback deployment.

---

### D.1.3 Medium Exposure

| ID | Risk | L | I | Mitigation | Trigger |
|---|---|---|---|---|---|
| **R-09** | Layering erodes under deadline pressure; the architecture becomes decorative. | M | M | Import-linter contracts as a merge gate (ADR-001). Not reviewable-by-eye — machine-enforced. | Any PR proposing to add an import-linter exception. |
| **R-10** | Scope creep: RAGStrike drifts toward becoming a RAG framework, a guardrail product, or a chatbot. | M | M | Non-goals NG1–NG5 are normative. Any feature contradicting them requires a superseding ADR. | Any issue proposing remediation *execution* rather than recommendation. |
| **R-11** | Detector false-positive flood on secrets/PII makes the tool noisy and ignored. | M | M | Entropy gating plus known-placeholder deny-lists; SecureRAG false-positive gate; detector firing-rate metrics as an operational signal. | Any detector with a firing rate near 0% or 100% across many scans. |
| **R-12** | Evidence storage grows unbounded on a developer laptop. | M | M | Retention policy: full evidence for the last N scans per target, older scans compacted to findings plus metrics. | Database exceeding a configured size threshold. |
| **R-13** | Report generation becomes the bottleneck or fails and loses findings. | L | M | `PARTIAL` scan state — findings persist independently of rendering; reports are always re-renderable from stored data. | Any `PARTIAL` scan in CI. |
| **R-14** | Ollama/Qwen3 availability or behaviour changes break the lab targets. | M | M | Model pinned by tag in Compose; lab smoke test in CI; the framework itself does not depend on the judge by default. | Nightly lab smoke test failure. |
| **R-15** | OWASP LLM Top 10 revision invalidates the mapping. | M | L | Mapping stored as data in the catalog, versioned, not hardcoded in detectors; a revision is a catalog update plus a report regeneration. | Publication of a new OWASP LLM Top 10 revision. |
| **R-16** | Windows/POSIX path and process differences break local development. | M | L | CI matrix across Linux, macOS, Windows; `pathlib` everywhere; bootstrap scripts for both shells. | Any platform-specific CI job failure. |
| **R-17** | Solo-maintainer bus factor; the project stalls. | M | M | Documentation-first culture (this SDD), ADRs recording *why*, the SDK lowering the contribution barrier, `CODEOWNERS` and a contribution guide from day one. | Sustained absence of external contributions after the SDK ships. |
| **R-18** | Legal/ethical misuse of the tool against unauthorized systems. | L | H | Authorization gate with a persisted record embedded in every report (ADR-017); loopback default; responsible-use policy; no evasion features; Apache-2.0 with an explicit usage statement in `SECURITY.md`. | Any report of use against a non-consenting third party. |

---

### D.1.4 Accepted Risks

| ID | Risk | Rationale for acceptance |
|---|---|---|
| **A-01** | Single-process execution caps throughput. | The bottleneck is target inference, not RAGStrike (ADR-018). The orchestrator interface is the seam if this ever changes. |
| **A-02** | No OS-level plugin sandbox in v1. | Declared honestly rather than falsely claimed. Manifest-first loading and declared permissions raise the bar; full isolation is v2. |
| **A-03** | Hallucination and citation packs depend partly on a capped LLM judge. | No deterministic oracle exists for these questions. Findings are labelled model-assisted and confidence-capped. The alternative — not testing them at all — is worse. |
| **A-04** | Similarity-based prompt-leakage detection has reduced confidence against unknown targets. | RAGStrike reports lower confidence rather than pretending to certainty it cannot have. |

---

## D.2 Development Milestones

Milestones map directly to the Phase documents. Each has a **binary exit criterion** — a condition that is either met or not, never "mostly."

| Phase | Milestone | Key deliverables | Exit criterion |
|---|---|---|---|
| **0** | **Architecture** | This SDD and its four annexes. | Approved. Every subsequent phase implements against these contracts. |
| **1** | **Engineering Foundation** | Repo scaffold per Annex A · `pyproject.toml` · ruff/black/mypy strict · **import-linter contracts** · pre-commit · `ci.yml` · logging setup · exception taxonomy · docs skeleton · `CONTRIBUTING`/`SECURITY`/`LICENSE`. | CI green on an empty codebase with all gates active. The dependency rule is enforced **before** there is any code to violate it. |
| **2** | **VulnerableRAG v1** | `packages/ragcore` · ingestion and query pipelines · `SecurityPolicy` seam · vulnerable profile with weaknesses V1–V9 · Streamlit UI with chunk/source display · corpus + manifest · Docker Compose (loopback) · lab safety controls. | Upload a PDF, ask a question, see retrieved chunks and sources. All nine weaknesses manually reproducible per `vulnerabilities.md`. |
| **3** | **RAGStrike Core** | Domain + contracts · config loader · aiosqlite repositories + migrations · `TargetAdapter` port · HTTP and local-Python adapters · scheduler · executor · evidence recorder · event bus · orchestrator · minimal CLI. | `ragstrike scan` runs a hardcoded probe set against VulnerableRAG end to end and persists evidence. No attack packs yet. |
| **4** | **Plugin Framework** | Manifest schema and parser · entry-point + directory discovery · compatibility resolution · registry with health reporting · detector registry · safe payload template engine · failure isolation. | A fixture pack installed via pip is discovered, scheduled, and executed with **zero edits under `core/`** (SC2). |
| **5** | **Attack SDK** | Base abstractions · scaffolding generator · schema validators · test doubles · pack and adapter conformance suites · **replay harness** · authoring documentation. | A pack authored from `sdk new-pack` passes conformance with no LLM, no network, and no Docker. |
| **6** | **Analyzer, Scoring, Reporting Spine** | Built-in detector catalog · noisy-OR aggregation · scoring model v1.0.0 · recommendation catalog · ReportModel + HTML/JSON renderers · API + dashboard. | A full scan of VulnerableRAG produces a complete HTML report with all ten sections and a hand-reproducible risk score. |
| **7** | **Injection Packs** | `prompt-injection` · `indirect-prompt-injection` · `role-override`. | All three detect on VulnerableRAG at declared minimums and produce **zero** findings on SecureRAG. |
| **8** | **Leakage Packs** | `prompt-leakage` · `secret-extraction` · `pii-leakage`. | Same bidirectional criterion. Secret detector false-positive rate zero on the SecureRAG corpus. |
| **9** | **Context Packs** | `context-injection` · `context-poisoning` · `context-window-overflow`. | Same criterion, plus: every poisoning case cleans up, and residuals are reported when cleanup is impossible. |
| **10** | **Analyzer Engine Maturity + Grounding Packs** | Detector hardening · golden evidence corpus · differential detector · `hallucination-evaluation` · `retrieval-integrity` · `citation-verification` · scan comparison. | **SC1 met in CI**: VulnerableRAG grades E/F, SecureRAG grades A/B, per-category minimums enforced. |
| **11** | **v1.0 Release** | SecureRAG completion and parity tests · PDF renderer · `openai_compatible` and `ollama` adapters · docs site · PyPI + Docker publication. | `pip install ragstrike` works from a clean machine; quickstart completes in under ten minutes. |

**Dependency note.** Phases 4 and 5 gate everything after them: no attack pack should be written before the plugin contract and the SDK conformance suite exist, or the packs will encode assumptions the contract does not guarantee and the first contract change will break all of them at once.

---

## D.3 Post-v1 Roadmap

### v1.x — Consolidation

| Item | Description |
|---|---|
| SARIF output | Native CI/code-scanning integration. |
| LangChain / LlamaIndex adapters | Test chains and query engines in-process. |
| Anthropic and additional provider adapters | Broader direct-model coverage. |
| Scheduled scans | Recurring posture monitoring with regression alerting. |
| Report diffing UI | Visual new/fixed/persisting across releases. |
| Payload pack marketplace index | Discoverability for community packs. |
| Localization | The string catalog (NFR-14) made real for additional languages. |

### v2.0 — Depth

| Item | Description |
|---|---|
| **Plugin sandboxing** | Subprocess isolation with a capability broker, retiring accepted risk A-02. |
| **Agentic target support (LLM06)** | Excessive-agency and tool-abuse testing against an action-side sandbox that records intended side effects without performing them. |
| **Multimodal injection** | Instructions embedded in images, audio, and structured documents. |
| **Adaptive attack generation** | Mutators that learn from what worked earlier in the same scan, within strict determinism-preserving bounds (seeded search, recorded trajectory). |
| **Embedding-space attacks** | Inversion and collision testing against the vector store directly (LLM08). |
| **Multi-turn crescendo** | Long-horizon strategies that escalate gradually across many turns. |
| **Guardrail fingerprinting** | Identifying which defensive product a target uses, and testing its known boundaries. |
| **Benchmark corpus** | A public, versioned corpus of targets and expected grades, so RAGStrike's own accuracy can be measured by third parties. |

### Explicitly Out of Scope, Permanently

Detection evasion. WAF bypass. Rate-limit circumvention. Mass or untargeted scanning. Any feature whose primary value is testing systems the operator is not authorized to test. These are recorded here so the boundary is not relitigated in every feature discussion.

---

## D.4 Definition of Done — v1.0

- [ ] All five success criteria (SC1–SC5) verified in CI.
- [ ] Twelve attack packs shipped, each with conformance tests and bidirectional validation.
- [ ] `mypy --strict` clean; ruff clean; import-linter contracts passing.
- [ ] Coverage ≥85% in `core/`, ≥70% overall.
- [ ] Documentation site published: quickstart, configuration, pack authoring, adapter authoring, report interpretation, responsible use, limitations.
- [ ] `pip install ragstrike` and `docker compose up` both work from a clean machine.
- [ ] Quickstart — install to first report — completes in under ten minutes.
- [ ] `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `LICENSE`, `CHANGELOG.md` present in both repositories.
- [ ] Every ADR in Annex C either implemented as written or superseded by a recorded ADR.
