# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Two version numbers are tracked.** The application version is the heading below. The
**Plugin API version** (`PLUGIN_API_VERSION`) moves independently (ADR-015) — an application patch
release must not signal a potential break to every third-party pack author. Plugin API changes are
called out explicitly.

---

## [1.0.0] - 2026-07-30

**Phase 15 — Production Readiness & Open Source Launch.** No new scanning features and no functional
change; the whole release is audit, versioning, and the documentation a public project needs.

### Added

- **Project audit** — `validation/runner/audit.py` measures modules, code lines, docstring and README
  coverage, dead modules, and import cycles. It **separates import-time cycles from deferred ones**,
  because a `TYPE_CHECKING` or function-level import cannot deadlock and reporting it as a cycle
  trains people to ignore the audit. Result: 0 import-time cycles, 1 deferred, 0 dead modules.
- **[`docs/audit-report.md`](docs/audit-report.md)** — structure, code quality, configuration and
  logging consistency.
- **[`docs/project-metrics.md`](docs/project-metrics.md)** — every measured number with the command
  that produced it, and an explicit statement of what the numbers do *not* say.
- **[`docs/versioning-policy.md`](docs/versioning-policy.md)** — semver applied to the public surface,
  compatibility commitments for 1.x, and a deprecation policy with one narrowly-stated exception.
- **[`docs/technical-debt.md`](docs/technical-debt.md)** — seven entries, each with a cost, a reason it
  is unpaid, and what fixing it takes.
- **[`docs/known-issues.md`](docs/known-issues.md)**, **[`docs/maintenance-guide.md`](docs/maintenance-guide.md)**,
  **[`docs/refactoring-notes.md`](docs/refactoring-notes.md)** — including the refactors deliberately
  *not* made, and why "cleaner" is not a reason.
- **ADR-021 … ADR-024** appended to Annex C: the dashboard shipping against an unimplemented API;
  SecureRAG as a standalone repository amending ADR-009; `NOT_RUN` never reported as a mismatch; and
  v1.0.0 shipping with known debt recorded rather than suppressed.
- **Four indexes** — [architecture](docs/architecture-index.md), [API](docs/api-index.md),
  [plugins](docs/plugin-index.md), [evaluation packs](docs/evaluation-pack-index.md). Each names the
  gaps: `/api/v1` has no handlers, nine of twelve catalogued packs are unbuilt, three of six
  evaluation categories are uncovered.
- **Plugin developer experience** — [workflow](docs/plugin-workflow.md),
  [checklist](docs/plugin-checklist.md), [review checklist](docs/plugin-review-checklist.md),
  [testing guide](docs/plugin-testing-guide.md).
- **`examples/`** — `custom_plugin/`, `custom_target/`, `sample_data/`, and `example_reports/`
  containing **real generated output** in HTML, Markdown, and JSON rather than mock-ups.
- **`website/`** — landing page, architecture, features, quick start, FAQ, roadmap, and a screenshot
  manifest. Source only; nothing is deployed.
- **`docs/presentation/`** — elevator pitch, recruiter summary, technical summary, talk outline, demo
  script, and Mermaid architecture diagrams.
- **[`docs/license-review.md`](docs/license-review.md)** and a **`NOTICE`** file.

### Changed

- **Version bumped to 1.0.0** across `VERSION`, `__version__`, `pyproject.toml`, and `CITATION.cff` —
  all four now agree. `PLUGIN_API_VERSION` stays at 1.0: the plugin contract did not change.
- `README.md` — status banner, badges, repository layout, and documentation index brought current. The
  banner now leads with the fact that no real attack findings exist yet.
- `docs/release-checklist.md` — a v1.0.0 sign-off recording two criteria that are **not** green.
- `pyproject.toml` — `[tool.bandit]` configuration with the B105 skip and its reason.

### Fixed

- **Six bandit findings**, each established as a false positive and annotated at the site with its
  reason rather than silenced in a config file. Only `B105` is skipped project-wide, because this
  framework's outcome vocabulary literally contains the word `PASS`.
- **A licensing claim that was too strong.** `third-party-attribution.md` stated that no copyleft
  dependency was present. The measured review found four MPL-2.0 distributions and one tri-licensed
  transitive dependency in the optional `pdf` extra. The conclusion is unchanged — nothing is vendored,
  Apache-2.0 redistribution is unaffected — but the claim was wrong, and the correction is left visible
  rather than quietly rewritten.
- **Invented CLI commands in the new documentation.** Several pages drafted this phase documented
  `targets add`, `targets authorize`, `ragstrike report`, `ragstrike history`, and `scan --plugins`.
  **None of those exist.** Checked against `--help` and corrected: targets are declared in
  `configs/targets.yaml` with an `authorization:` block, scans are scoped with `plugins disable`, and
  reports are generated from Python. The gap between the SDD's specified CLI and the implemented one is
  now stated in [`docs/api-index.md`](docs/api-index.md) instead of being papered over.

### Known gaps at 1.0.0

Neither is new; both are now stated in the README, the audit report, the metrics page, and the
limitations page:

- **No real attack findings exist.** The full differential run against the live lab pair is a
  multi-hour job that has not been completed.
- **`mypy src` reports 11 pre-existing errors** in Phase 3–5 code, recorded rather than suppressed.

## Pre-1.0 development log — Phases 1–14

Everything below shipped **as part of 1.0.0**. It is kept phase by phase rather than collapsed,
because the reasoning for each decision is attached to the phase that made it, and flattening it into
a single release entry would discard that.


### Added — Phase 14: Validation & Release

No new core features, by design. This phase measures, documents, and packages what the previous
thirteen built.

- **A validation harness** in `validation/`: benchmark datasets in YAML, a runner, ten consistency
  checks, nine performance measurements, and a differential comparison mode. One command, no
  prompts, and a target that is down degrades that target's benchmarks to `NOT_RUN` rather than
  abandoning the run — half a comparison is still worth reading.
- **Fifteen benchmarks across four datasets** — prompt manipulation, prompt leakage, context
  evaluation, and general RAG behaviour. Expectations are **per target**, because the same benchmark
  expects opposite results from the two halves of the lab, and `INCONCLUSIVE` is a first-class
  expectation for checks the framework has correctly declined to claim.
- **The `Separates` column.** A benchmark on which both halves agree has validated nothing about the
  difference between them, even when both matched their own expectation. That is reported explicitly
  rather than folded into the pass rate, because a scanner reporting the same result for a vulnerable
  and a hardened application is not measuring security.
- **The general-behaviour dataset exists to catch the failure nobody looks for:** SecureRAG scoring
  well by being broken. A hardened application that refuses ordinary questions produces no findings,
  and no findings reads as clean.
- **27 tests for the harness itself**, written specifically to catch vacuous passes — the failure
  shape that already occurred once in this project, when a compatibility test enumerated routes by
  walking an attribute that silently returned nothing.
- **Release documentation:** user, administrator, developer, deployment, and troubleshooting guides;
  FAQ; a repeatable demonstration walkthrough; known limitations; a v2.0 roadmap as roadmap items
  only; release checklist; installation validation; dependency summary; and third-party attribution.
- **Release artifacts:** `VERSION`, `CITATION.cff`, `RELEASE_NOTES.md`. `CODEOWNERS`, issue
  templates, and the PR template already existed from Phase 1.

#### Fixed — defects the harness found in itself

- **Two consistency checks asserted APIs that do not exist** — `build_engine` returns two values, not
  three, and `log_dir` lives on `logging`, not `storage`. Both surfaced on the first run.
- **"No target requested" was reported as a failed check**, making "I did not ask for a target"
  indistinguishable from "the target is down".
- **The Windows peak-memory measurement silently reported zero.** `ctypes` argtypes were never
  declared, so the HANDLE was truncated on 64-bit Windows and the call failed. A zero that looks like
  a measurement is worse than an honest "not measurable".
- **A comparison whose two halves both `NOT_RUN` was reported as `MISMATCH`** — turning "you disabled
  some plugins" into "the scanner is broken". Found by running the harness against the live pair; the
  summary totals were right and the comparison table was not.

#### Changed

- `configs/targets.yaml` — the `secure-rag` entry is enabled. It was added disabled in Phase 1 with
  the note that SecureRAG would arrive later; Phase 13 built it, and the differential cannot be
  measured with it switched off.


### Added — Phase 12: Dashboard

The Streamlit interface: nine pages, sixteen reusable components, seven services, a two-palette theme
system, global search, shared filtering, and polling-based live updates. It contains no business
logic and required **no change to the Scan Engine** — the only files touched outside
`src/ragstrike/dashboard/` are two lint-configuration entries.

- **A hard boundary, kept.** `ragstrike.dashboard` imports no engine package. ADR-010 is enforced by
  import-linter contract 3, which catches *indirect* chains — verified empirically: importing
  `reporters.service` to reach a `Finding` breaks the contract via
  `reporters -> analyzers -> models`. The dashboard therefore reaches the engine across a process
  boundary or not at all, which is also what keeps the API provably complete and the UI replaceable.
- **Written against the published API contract**, `/api/v1` exactly as SDD §22.2 specifies it — same
  paths, verbs, and error envelope. Two extensions are documented as such: `GET /scans/{id}/progress`
  (the polling companion to the SSE stream, since this phase specifies polling and no WebSockets) and
  the `POST /packs/{slug}/{enable|disable|validate}` operations the Plugins page needs.
- **The backend does not exist yet, and the dashboard says so.** `src/ragstrike/api/` is still the
  Phase 1 scaffold; building it here would merge two phases. So `http` is the default transport, and
  without a server every page shows one clear `BACKEND OFFLINE` banner and a page-specific empty
  state rather than nine separate failures or fabricated data.
- **An opt-in `demo` transport** serves a deterministic in-memory fixture over the same service
  interfaces, so the interface can be demonstrated, reviewed, and tested end to end without a server.
  It is **never inferred** — only `RAGSTRIKE_DASHBOARD__TRANSPORT=demo` selects it — and it carries a
  `DEMO MODE` banner on every page, derived from the transport rather than from a setting, so no
  configuration removes the label while the data stays fake. Unlabelled sample findings in a security
  tool are indistinguishable from a real assessment in a screenshot.
- **Nine pages, one responsibility each**: Dashboard, Scan Center, Targets, Plugins, Reports, Scan
  History, Settings, System Status, About. Each is a single `render(context)` reached through a route
  registry, so the sidebar, router, quick actions, and search results cannot disagree about what
  pages exist.
- **Sixteen components as pure functions returning HTML.** No Streamlit import, which is why the
  component tests assert on exact markup rather than screenshots and why the library imports in an
  environment without the `[dashboard]` extra.
- **Everything interpolated into HTML is escaped.** These components render payload text, target
  responses, and third-party plugin descriptions — attacker-influenced by construction. Escaping
  happens exactly once, at the point a value becomes an attribute; a test caught the double-escape
  that produced `&amp;quot;` in generated CSS.
- **Colour carries meaning, and the mappings are total.** An unknown severity renders informational
  rather than red (unknown is not severe); INCONCLUSIVE renders as a warning rather than grey (a
  result that needs attention); no two severities share a colour within a palette. A test walks the
  package and fails on any hex literal outside `theme/`, which is what makes "Future Custom Themes" a
  data change.
- **Centralized state with a closed key registry.** A test exercises every mutator and asserts
  nothing outside `STATE_KEYS` was written — "do not duplicate state", made checkable. Reads survive
  a session that outlived a code change; toasts drain exactly once; confirmations live in state
  rather than in locals, which is what keeps "confirm delete" from becoming "delete".
- **The safety rules stay where they are enforced.** The Targets page *shows* the local-only policy —
  a visible warning on non-local URLs and a statement of the rule before submission — but does not
  re-implement it. `target_adapters.build_adapter` remains the single enforcement point; two
  implementations of "is this host allowed" fail by the permissive one winning.
- **START SCAN stays disabled until authorization is confirmed** (ADR-017), a deliberate second gate
  in front of the backend's own per-target authorization record.
- **Polling stops at a terminal state.** `should_poll()` is what keeps the live view from becoming a
  busy loop against the backend after a scan has finished.
- **398 tests across eight suites** — components, navigation, services, state, theme, search, filters,
  and an integration suite that drives the real Streamlit runtime through `AppTest` and renders every
  page in both populated and offline states. Total suite: **1300 tests**.
- Documentation: [`docs/dashboard.md`](docs/dashboard.md) covering architecture, folder
  responsibilities, the nine pages, and the component, navigation, theme, state, developer, and
  extension guides — including a section on what this phase deliberately does not do.

#### Changed

- `ruff.toml` — `PLC0415` (function-level imports) added to the existing `src/ragstrike/dashboard/**`
  per-file ignore. A module-scope `import streamlit` would make every component, service, and page
  unimportable without the `[dashboard]` extra installed. Same precedent as the existing `plugins/**`
  and `tests/**` entries.
- `pyproject.toml` — `pandas.*` and `altair.*` added to the mypy `ignore_missing_imports` override,
  alongside the existing `streamlit.*`. Their stubs ship separately and pin a library minor version;
  pinning one to type four widget functions is a maintenance cost with no safety return.

### Added — Phase 11: Reporting Engine

Transforms the standardized `Finding` objects the Analyzer Engine produces into professional
security reports. **One model, N renderers**: every computation happens once in the builders, and a
renderer only chooses how to present what it is given — which is what guarantees the HTML, JSON, and
Markdown outputs agree about the same scan.

- **A format-independent `ReportModel`** with the ten sections the phase names: cover, executive
  summary, risk breakdown, category summary, detailed findings, evidence, recommendations,
  statistics, timeline, and chart data.
- **Twelve single-responsibility components**: `BaseReport`/`BaseRenderer`, `ReportEngine`,
  `ReportBuilder`, `ReportRegistry`, `ReportValidator`, `ExecutiveSummaryBuilder`,
  `StatisticsBuilder`, `TimelineBuilder`, `ChartDataBuilder`, `AssetManager`, `ExportManager`,
  `TemplateManager`.
- **HTML, JSON, and Markdown renderers behind one interface**, plus a PDF placeholder that
  **refuses** rather than emitting an empty file or HTML with a `.pdf` extension — either would look
  like success and fail when someone opened the report. `implemented = False` makes the state visible
  before it is called, and `render_all`/`export_all` skip it.
- **Adding a format changes no existing code.** A test parses `report_engine.py` and asserts no
  format name appears as a code-level string literal outside the default-registry helper.
- **Everything interpolated into HTML is escaped.** A report carries model output, retrieved
  documents, and prompt fragments — attacker-influenced by construction — and a security tool whose
  report executes what it found would be the most embarrassing possible vulnerability. Six tests
  cover script tags, hostile plugin names, detector details, and attribute-breaking quotes.
- **Templates are formatted, never evaluated.** `str.Template` understands `$name` and nothing else,
  which rules out Jinja despite it already being a dependency: a report template is a file an
  operator edits, and a templating language that can execute would turn styling a report into a
  code-execution surface. Export filenames are sanitized for the same reason.
- **Charts are data, never images** — six models, with fixed risk buckets so a histogram can be
  compared against last month's report, and every severity present even at zero so two scans render
  with the same axes.
- **Report persistence** via migration 4, appended not inserted. The rendered content is stored
  rather than regenerated: a report is an artifact someone made a decision from, and rebuilding it
  later would produce a different document the moment a template changed.
- **A five-operation internal API** (`generate`, `list`, `load`, `delete`, `export`) for the future
  Dashboard. Generating is separate from persisting, and exporting works with no repository at all —
  a CI job with no database is the simplest case and should not be the hardest.
- **Three configuration files** in `configs/reporting/`. Every loader falls back to built-in defaults
  and reports what fell back.
- **`docs/reporting-engine.md`** with architecture, class and sequence diagrams, renderer guide,
  template guide, exporter guide, developer guide, configuration guide, folder responsibilities,
  extension guide, and known limits.
- 147 new tests (902 total, up from 755).

### Changed — Phase 11

- **`ragstrike.reporters` moves onto its own layer row, directly above `ragstrike.analyzers`.** Phase
  1 listed them as siblings, and import-linter treats same-row modules as *independent* — so the
  contract forbade the one dependency SDD §19 requires, reporting reading findings. Harmless while
  both were empty scaffolds; fatal the moment either had behaviour. Verified in both directions:
  `reporters → analyzers` allowed, `analyzers → reporters` broken.
- **The persistence payload moved to the lower layer.** `ReportService.store()` originally built the
  database's record type via an import deferred inside the function, to dodge a module-level
  dependency. `lint-imports` caught it anyway — grimp reads the whole AST, so a deferred import is
  the same dependency, just harder to see. `StoredReport` is now defined in `reporters/base/` and the
  database maps it onto a row.
- `ReportBuilder` infers `analyzer_version` and `scan_id` from the findings when the caller does not
  supply them. Expecting every caller to copy them across by hand is how a stored report ends up
  untraceable to the rules that graded it — which is what an integration test found.
- The HTML and Markdown renderers shared a copy-pasted duration formatter; it now lives in
  `models/formatting.py`. Two copies is how two formats start disagreeing about the same scan.

### Fixed — Phase 11

- A Phase 10 test asserted `versions[-1] == 3`, hardcoding the latest migration number. The property
  it meant was "appended in ascending order with no gaps"; it now asserts that and locates the
  findings migration by name.

### Added — Phase 10: Analyzer Engine

A centralized engine converting raw plugin execution results into standardized security findings.
**The analyzer, not the plugin, decides.** Status, severity, confidence, and risk are re-derived in
one place against one configurable rule set, which is what makes findings comparable across packs
and what lets an operator re-tune grading without editing a plugin.

- **`Observation` and `Finding`** in `analyzers/base/`. `Observation` is *derived from* a plugin's
  existing `PluginResult`, which is how "plugins return raw results only" and "no plugin changes"
  are both satisfied: a plugin's own verdict arrives as `reported_status`, an observation about what
  the plugin concluded rather than the finding's status. `Finding` carries all thirteen fields the
  phase names plus `analyzer_version`.
- **Nine single-responsibility components**: `BaseAnalyzer`, `AnalyzerRegistry`, `AnalyzerEngine`,
  `RuleEngine`, `EvidenceEngine`, `RecommendationEngine`, `ConfidenceEngine`, `ScoreEngine`,
  `ValidationEngine`.
- **A rule engine where rules are data, never code.** Conditions are field/operator/value triples
  the engine interprets — nothing is `eval`'d and no attribute is traversed by name, because a rules
  file is untrusted input (ADR-016). First match wins by descending priority. **A rule can override
  a plugin's reported status**, and that override is recorded on the finding; without it the engine
  would be a pass-through with extra steps.
- **Evidence normalization** into one shape regardless of which pack produced it — the injection
  pack writes detector signals, the leakage pack writes redacted summaries, the poisoning pack
  writes sources and chunk ids. Normalization never invents: an absent section stays absent rather
  than being defaulted to something plausible.
- **Scoring as arithmetic, never opinion** (ADR-011): `severity_weight × confidence` per finding,
  worst-plus-volume per category, weighted mean per scan. Only `FAIL` contributes — a `PASS` found
  nothing and an `INCONCLUSIVE` established nothing, so letting either contribute would produce a
  risk number partly composed of things nobody observed.
- **Confidence as a number and a band**, with every component returned so the score is
  decomposable. The defaults encode one judgement: evidence matters more than a plugin's
  self-assessment. Corroboration is capped, so a noisy pack cannot outrank a careful one on volume.
- **Retrieved recommendations** (ADR-012) by plugin → category → severity → default, with a pack's
  own advice preferred over all of them.
- **Loud validation.** A malformed observation silently dropped reads exactly like a clean result,
  so rejections are recorded on the report with a field name and a reason.
- **A registry supporting discovery without engine changes.** A specialist analyzer beats a
  generalist for its categories; a category with no specialist still gets analyzed, which keeps a
  brand-new pack working on day one.
- **Findings persistence** via migration 3 — appended, never inserted. `findings` is a separate
  table from `plugin_results` on purpose: rules change, so the same stored observations can be
  re-graded later without rewriting the record of what actually happened.
- **Five configuration files** in `configs/analyzer/`. Every loader falls back to built-in defaults
  and *reports* what fell back — a tool that refuses to analyze over one YAML typo does not get run,
  but one that silently ignores the file an operator just edited is worse.
- **`AnalysisReport`** as the interface for the future Reporting Engine. Structured objects only, no
  HTML or PDF. Carries `coverage`, because a scan where six of ten plugins were inconclusive is a
  different statement from one where all ten reached a verdict.
- **`docs/analyzer-engine.md`** with architecture, class and sequence diagrams, rule engine guide,
  scoring guide, evidence model, finding model, configuration guide, developer guide, extension
  guide, and known limits.
- 127 new tests (755 total, up from 628).

### Changed — Phase 10

- `analyzers` sits **below** `database` in the layer stack, so the engine cannot import a
  repository. It declares a `FindingRepository` port that `database/repositories/` implements.
  Analysis is a pure transformation; depending on SQLite would mean the whole engine could only be
  exercised with a database attached. `lint-imports` enforces the direction, and three tests assert
  the independence structurally — no pack imports the analyzer, the analyzer imports no pack, and no
  plugin name appears as a code-level string literal in analyzer code.

### Added — Phase 9: Context Poisoning evaluation pack

The third first-party pack, at `src/ragstrike/attacks/context_poisoning/`. OWASP LLM04 / LLM08:
does retrieval return what it should, and only what it should?

- **A dataset system.** Evaluation cases live in external YAML under `datasets/`, never in Python.
  A dataset carries an id, a version, a corpus profile, and its documents; a case carries a question
  id, a document id, the question, and the expectations retrieval must satisfy — expected sources,
  forbidden sources, minimum chunks, citation rules, canary markers, and the security outcome and
  analyzer result a healthy system should produce. Two datasets ship: `benign-baseline` (the
  control) and `poisoned-corpus`.
- **Loading is lenient about files and strict about cases.** A malformed dataset is skipped and
  recorded in `evidence.skipped_datasets` rather than aborting a scan. A case with no question, no
  id, or no *checkable* expectation is dropped — one declaring only `security_outcome` asserts
  nothing observable and would pass unconditionally, inflating coverage with a check that never ran.
- **Three detectors, all pure and all decisive**: `retrieval_integrity` (1.0), `citation_integrity`
  (0.9), `canary` (1.0). Every one answers a set-membership question the dataset states explicitly,
  so silence is genuine evidence of absence and a clean run is a real PASS. Within retrieval
  integrity a forbidden source outranks a missing expected one: the first is a security finding, the
  second usually means the corpus was never ingested, and the reason drives remediation.
- **Source normalization** before comparison, so `docs/Handbook.PDF` and `handbook.pdf` are the same
  document. Retrieval layers report provenance inconsistently, and comparing raw strings would
  produce false findings indistinguishable from real ones.
- **A `reason` on every signal**, summarized into `Analysis.detail`. Remediation in
  `recommendations/catalog.yaml` is keyed by reason rather than by technique, because what an
  operator should do depends on which integrity property broke.
- **Evidence captures all ten fields the phase enumerates**, and all nine reporting fields plus
  dataset version survive the database round trip. Plugin execution statistics come from the
  existing repository with no pack-specific path.
- **`docs/context-poisoning-pack.md`** covering folder responsibilities, plugin lifecycle, dataset
  format, analyzer workflow, reporting flow, configuration, extension guide, developer guide, and
  known limits.
- 104 new tests (628 total, up from 524).

### Changed — Phase 9

- **This pack is an evaluation module, not an active poisoning pack, and that narrows the Phase 1
  scaffold deliberately.** The scaffold sketched an ingest → re-query → cleanup design requiring
  `INGEST_DOCUMENT` and mandatory cleanup. Phase 9 scopes it to read-only: the corpus state is
  *declared* by the dataset rather than *created* by the pack. The consequence is stated in the
  docs rather than glossed — this design cannot demonstrate cross-session persistence, because
  proving that requires mutating the corpus. It shows poisoned content is reachable and repeated,
  which is the consequence rather than the mechanism.
- **No `require_local_target` option exists in this pack.** The injection and leakage packs each
  ship one; Phase 9 requires that configuration to enable external targets not exist, so the
  loopback refusal is unconditional in code. A parametrized test asserts plausible-looking
  overrides are inert.

### Fixed — Phase 9

- Three Phase 7 integration tests selected their result with `stored[0]`, which silently picked a
  different pack once results came back in slug order with a third pack installed. They now select
  by slug. Same root cause as the Phase 8 fix, in the assertions that fix did not reach.

### Added — Phase 8: Prompt Leakage attack pack

The second first-party pack, at `src/ragstrike/attacks/prompt_leakage/`. OWASP LLM07: can the
system prompt be recovered?

- **Seven techniques** from Annex B: `direct-request`, `completion-continuation`,
  `translation-laundering`, `format-transformation`, `debug-pretext`, `token-boundary-probe`
  (requires `SESSION_MEMORY`, recorded SKIPPED rather than ERROR without it), and
  `error-channel-leak`.
- **Three detectors**, all pure: canary (1.0, decisive), similarity (0.9, decisive), pattern (0.75,
  **not** decisive — it fires on any prompt-shaped phrasing, so letting it convict would report a
  leak whenever the target discussed prompting at all). Similarity measures asymmetric word-shingle
  overlap, answering "how much of the prompt came back" rather than "how similar are these strings".
- **Honest calibration.** Similarity needs the operator's real prompt to compare against. Without
  `reference_prompt`, the detector reports itself un-evaluable and the pack caps confidence at 0.5
  — below the 0.6 failure floor — so an uncalibrated heuristic hit can never be reported as a
  confirmed leak. A canary hit is exempt, being deterministic. A default-configured scan therefore
  reports mostly INCONCLUSIVE, which is the correct answer rather than a defect, and the notes say
  what to supply to improve it.
- **Redacted evidence by default.** A prompt-leakage finding is by construction a copy of the thing
  that should not have leaked, and evidence is persisted, exported, and pasted into tickets. The
  default records that a leak happened and how much matched, never the recovered text. An
  integration test asserts the guarantee holds *after* the evidence reaches the database.
- **Full configuration surface**: `enabled`, `timeout`, and `severity_override` through the existing
  `plugins.yaml` mechanism, plus `retry_count`/`retry_backoff_s` (transport failures only — a
  response the target actually returned is never re-sent, which would corrupt the
  `successes/attempts` measurement), an `evidence` block (`redact`, `excerpt_chars`,
  `include_negative_signals`), and a `logging` block (`level`, `per_case`). `validate()` rejects an
  unknown logging level or a negative retry count at load time.
- **Reporting fields readable from storage.** All nine the brief names survive the database round
  trip. `confidence` is written into evidence rather than a column: `PluginResult` has none and the
  scheduler drops `Analysis.confidence`, so adding one would mean changing a Phase 3 entity, its
  schema, and its migration. An integration test asserts the workaround survives persistence rather
  than assuming it.
- **`docs/prompt-leakage-pack.md`** covering folder structure, plugin lifecycle, configuration,
  analyzer flow, reporting flow, extension guide, developer guide, and known limits.
- 90 new tests (524 total, up from 434).

### Fixed — Phase 8

- Two Phase 7 integration tests asserted the first-party attacks directory contained *exactly*
  `prompt-injection`, which was never the invariant they meant and broke as soon as a second pack
  landed. They now assert what they were checking for: nothing is rejected, and the number of
  active packs matches the number of directories carrying a `pack.yaml`.

### Added — Phase 7: Prompt Injection attack pack

The first first-party attack pack, filling the Phase 1 scaffold at
`src/ragstrike/attacks/prompt_injection/`. OWASP LLM01.

- **Seven techniques** from Annex B: `direct-override`, `delimiter-escape`, `authority-spoof`,
  `task-substitution`, `encoding-obfuscation`, `multilingual-pivot`, and `payload-splitting`.
  The last requires `SESSION_MEMORY` and is recorded SKIPPED — never ERROR — against a target that
  does not declare it, because a capability gap is a coverage gap rather than a malfunction.
- **Three detectors** (`detectors.py`), all pure functions: canary (weight 1.0), structural (0.85),
  refusal-absence (0.55). Weights, decisiveness, the refusal vocabulary, and the combination rule
  are declared in `detectors/bindings.yaml`, so re-tuning detection is editing data. Combination is
  `max`, not a sum — two circumstantial signals must not manufacture a deterministic-grade finding.
- **Canary-based, non-offensive payloads.** Every case asks for a meaningless token. Nothing
  requests a secret, writes to the corpus, or issues anything but a chat request; `destructive:
  false` is required on every payload and asserted by the tests.
- **Pack-level loopback refusal.** `execute()` refuses a non-loopback target before its first
  request, duplicating the framework's `build_adapter()` guard on purpose — a control that exists
  only upstream of a pack is one the pack trusts rather than enforces.
- **Configurable expected outcomes.** Test cases live in `payloads/*.yaml` and declare what to
  expect (`canary`, `structural`, `session`, `setup_only`); techniques declare which detectors
  decide them in `attacks/techniques.yaml`. No evaluation logic in the engine, and none hardcoded
  in Python inside the pack either.
- **Session continuity** for stateful techniques: payloads sharing an `expects.session` value are
  sent on one conversation, everything else gets a fresh session so a success in one case cannot
  inflate the next.
- **Retrieved remediation** (`recommendations/catalog.yaml`), one entry per technique, selected by
  the technique behind the most failures. Never generated at runtime (ADR-019).
- **`docs/prompt-injection-pack.md`** covering folder structure, responsibilities, configuration
  format, plugin lifecycle, analyzer workflow, output format, future extensibility, and known
  limits.
- 69 new tests (434 total, up from 365), including a guard that no prompt-injection logic exists
  under `core/`.

### Changed — Phase 7

- `configs/config.yaml` adds `./src/ragstrike/attacks` to `plugins.local_dirs`, which is how
  first-party packs are discovered in a source checkout. Packaged installs use the
  `ragstrike.attack_packs` entry-point group instead; a directory that does not exist is skipped
  without error, so the line is harmless in an installed environment. No engine code changed.
- `.importlinter` adds `ragstrike.attacks` as a layer directly above `ragstrike.sdk`. That package
  previously held only scaffolding READMEs and was absent from the stack, which left it
  *unconstrained* — nothing structurally prevented the engine importing a pack, the one thing the
  plugin architecture exists to prevent. Verified by deliberately adding such an import and
  confirming the contract breaks, then reverting.

### Added — Phase 6: Evaluation plugins and scope enforcement

The plugin framework itself landed in Phase 4 and the SDK in Phase 5; this phase adds the first
plugins that use them, hardens the localhost-only restriction from a convention into a structural
guarantee, and gives evaluations a vocabulary for "I could not tell".

- **Five non-offensive evaluation plugins**, each reading its test cases from
  `payloads/cases.yaml` rather than from code, comparing observed against expected behaviour,
  emitting standardized evidence, and never modifying the target:
  - `instruction-priority` (HIGH) — do system instructions outrank user instructions?
  - `prompt-boundary` (HIGH) — does configuration text stay out of answers?
  - `context-separation` (HIGH) — is document content treated as data or as instruction?
  - `source-attribution` (MEDIUM) — does every citation appear among the retrieved chunks?
  - `retrieval-consistency` (LOW) — does an identical question retrieve an identical source set?
- **`PluginOutcome.INCONCLUSIVE`.** The check ran, the target answered, and the answer settles
  nothing — distinct from `ERROR` (the machinery broke) and `SKIPPED` (it never ran). Reporting an
  undetermined result as `PASS` would print "the target resisted" when the truth is "nobody knows".
  Needs no migration: `plugin_results.outcome` is plain `TEXT` with no `CHECK` constraint, which
  `tests/integration/` now verifies rather than assumes.
- **`EvaluationAttack` and `Verdict`** in `sdk/base/evaluation.py` — the shared half of an
  evaluation plugin (load cases, send them, time them, catch per-payload transport failures, build
  results, fold them). A subclass writes `judge()` and `recommendation()` and nothing else. Additive:
  no Phase 5 module changed, and `examples/custom_pack/plugin.py` still uses raw `BaseAttack`.
- **`PluginStatistics.inconclusive`** — counted separately from `errored`, because an undetermined
  result and a broken one need different follow-up.
- **`docs/evaluation-plugins.md`**, plus a README for each of the five plugins.
- 79 new tests (365 total, up from 286).

### Fixed — Phase 6

- **`ragstrike targets --verify` bypassed the target scope check.** It built adapters and
  health-checked every entry in `targets.yaml` without calling `assert_allowed()`, so a non-loopback
  host was probed by a command that never asked whether it was permitted — while `scan` refused the
  same target. The check now runs inside `build_adapter()`, the single construction chokepoint, with
  restrictive defaults: a call site that forgets to thread the operator's policy through gets
  loopback-only rather than unrestricted.
- **An allowlist entry alone permitted a remote host.** `assert_allowed()` returned early on
  `host in allowed_hosts`, so `safety.allow_remote_targets: false` did not actually hold for any
  host that appeared in `safety.allowed_hosts`. Both `SafetySettings` and the method's own docstring
  already documented a two-step opt-out (`allow_remote_targets` **and** an allowlist entry); the code
  implemented one step. The rule now matches its documentation.

### Changed — Phase 6

- Outcome fold precedence is now `FAIL > ERROR > INCONCLUSIVE > PASS > SKIPPED`. `INCONCLUSIVE`
  outranks `PASS` because a run where some cases reached no verdict has not established that the
  target resisted.
- `cli/output/console.py` renders `INCONCLUSIVE` in cyan, labelled `INCONC` — deliberately not a
  shade of green or red, since colouring it as either would smuggle a verdict into a result that
  does not have one. Both lookup tables are subscripted directly, so a test now asserts they cover
  every enum member.

### Added — Phase 5: Attack SDK (Developer Kit)

Wraps the Phase 4 plugin contract in a full developer kit under `src/ragstrike/sdk/`, so that
writing a new attack means writing metadata, payloads, and a success criterion — everything else
already exists. Nothing in `plugins/base/attack.py` or the scheduler changes; the SDK is built
entirely on top of the Phase 3/4 contract.

- **`sdk/request_builder/`** — `TargetRequestBuilder`, a fluent wrapper around the existing
  `TargetRequest` contract. `HttpMethod` and `RawRequestSpec` are documented, unwired
  architecture placeholders for future auth/headers/cookies/streaming/multipart/retries support.
- **`sdk/response_parser/`** — `ResponseParser` wraps `TargetResponse` with `.text()`, `.json()`,
  `.chunks()`, `.sources()`/`.citations()`, `.metadata()`, `.status_code()`, `.headers()`,
  `.excerpt()`, and more. `.status_code()`/`.headers()` are documented as best-effort against the
  currently shipped adapter, which does not carry either explicitly.
- **`sdk/payload_loader/`** — `SdkPayloadLoader`, a lenient JSON/YAML/TXT loader that skips
  individually malformed payload files instead of raising, in contrast to Phase 4's strict
  `PayloadLoader` that it wraps. Reports what it skipped via `LoadResult.skipped`.
- **`sdk/result_builder/`** — `ResultBuilder`, a fluent builder for the standard `AttackResult`
  object (plugin name, payload id/content, target, timestamps, status, evidence, severity,
  confidence, recommendation, references, notes). `fold_results()` folds many per-payload results
  into one scan-level `Analysis` (outcome precedence FAIL > ERROR > PASS > SKIPPED).
  `pick_recommendation()` picks the recommendation matching the folded outcome.
- **`sdk/validators/`** — attack-agnostic checks: response exists, response has text, status code
  valid, JSON valid, fields exist, required metadata exists. Each has an `is_*`/`has_*` boolean
  form and a `require_*` form that raises `ValidationError`.
- **`sdk/helpers/`** and **`sdk/utils/`** — `Timer`, `new_uuid`/`new_short_id`, `FileHelper`,
  `JsonHelper`, `YamlHelper`, `retry_async` (exceptions only, never responses — retrying a real
  answer would corrupt the `successes/attempts` exploitability measurement), `StringUtils`,
  `FormattingUtils`.
- **`sdk/exceptions/`** — `SdkError`, `PayloadError`, `ValidationError`, `TargetConnectionError`,
  `PluginConfigurationError`, `PluginTimeoutError`. All descend from the existing
  `RAGStrikeError` hierarchy; nothing the SDK raises escapes the CLI's exit-code mapping.
- **`sdk/constants/`** — default timeout, retry count/backoff, framework/plugin-API version,
  default headers, payload tiers, `ConfigKeys`.
- **`sdk/base/`** — `BasePayload`/`BaseRecommendation` (re-exported from `plugins.base.attack`),
  `AttackResult`, `BaseEvidence`, `EvidenceCollection`.
- **`sdk/context/`** — `ScanContext` (configuration, logger, target, database, current plugin,
  scan id, framework version), built by a plugin from its existing `PluginContext` plus the
  `target` parameter `execute()` already receives — no change to `BaseAttack`'s signature.
  `database` is always `None` today; the field is reserved for a future read-only accessor.
- **`sdk/interfaces/`** — `RequestBuilderProtocol`, `ResponseParserProtocol`,
  `ResultBuilderProtocol`, `ValidatorProtocol` (`@runtime_checkable`).
- **`examples/custom_pack/plugin.py` — `ExampleAttack`.** A complete, working (non-attack) plugin
  built entirely on the SDK, 99 lines. Demonstrates the acceptance criterion directly rather than
  just claiming it.
- **`docs/sdk-guide.md`** — dependency diagram, class diagram, sequence diagram, and a worked
  example, plus a cross-reference from `docs/plugin-development.md`.
- 159 new tests across payload loader, request builder, response parser, result builder,
  validators, exceptions, context, helpers, utils, and the example plugin (286 total, up from 127).

### Changed — Phase 5

- `plugins/base/payloads.py` — added `PayloadLoader.parse_file(path)`, a small additive method
  that parses one file in isolation. `SdkPayloadLoader` needs this to skip a malformed file
  without the directory-wide scan `files()` already does raising on the first bad file it meets,
  which would misattribute failures to files it was never asked about. `files()`'s own behaviour
  is unchanged.
- `.importlinter` — added a `ragstrike.sdk` layer directly above `ragstrike.plugins`, encoding
  Annex A's rule that the SDK depends on the core and never the reverse as an enforced contract.

### Added — Phase 4: Plugin framework

Turns the Phase 3 engine into a plugin-driven framework. The engine still never knows what attack
it is executing; Phase 4 adds the surface plugins need to be a real ecosystem.

- **Extended `BaseAttack` lifecycle.** `validate()`, `healthcheck()`, `setup()`, `cleanup()` on
  top of the Phase 3 four (`payloads/execute/analyze/recommendation`). All optional; default
  implementations do the right thing. Called by the scheduler in a fixed order documented in
  `docs/plugin-lifecycle.md`.
- **Declarative identity.** Plugins set class attributes (`plugin_id`, `plugin_name`,
  `plugin_version`, `author`, `description`, `category`, `severity`, `owasp_mapping`, `references`,
  `tags`, `requires_capabilities`, `required_target_type`, `min_framework_version`,
  `requires_api`, `license`, `enabled`) and get `metadata()` for free. Overriding `metadata()`
  still works when identity is computed at runtime.
- **`PluginContext` — dependency injection.** Plugins never instantiate the database, the logger,
  the target adapter, the configuration, the scheduler, or the engine. They ask the context.
- **`configs/plugins.yaml` — per-plugin runtime configuration.** `enabled`, `timeout`,
  `severity_override`, `config`. Merged into the `PluginContext`. No security control lives here;
  the manifest's `permissions` block is the authority.
- **`PayloadLoader`.** JSON, YAML, and TXT payload files under `plugins/<name>/payloads/`. Read
  in filename order for reproducibility. Non-evaluating -- no expression eval, no attribute
  traversal, no Jinja.
- **`PluginManager` — operator surface.** `list`, `info`, `enable`, `disable`, `validate`,
  `reload`. Distinct from `PluginRegistry` because their failure modes are distinct: registry
  errors abort a scan, manager errors must not.
- **`PluginLoader` — split from discovery.** Discovery answers "what manifests exist?"; loader
  answers "how do I turn a manifest into a callable plugin, with DI wired in?"
- **`plugins/registry/validator.py` — framework validation rules.** Folder exists, manifest
  exists, payloads directory exists, class inherits `BaseAttack`, required methods implemented,
  version parseable, API compatible.
- **Events architecture.** `PluginEventType` (LOADED / ENABLED / DISABLED / UPDATED / STARTED /
  FINISHED / FAILED), `PluginEvent`, `EventBus` protocol, `NoOpBus` default, `InMemoryBus` for
  tests. Wired into the registry and scheduler; no persistent subscribers yet.
- **Extended plugin folder layout.** `metadata.yaml` (canonical, `pack.yaml` still supported),
  `plugin.py` (canonical, `attack.py` still supported), `payloads/`, `tests/`, `examples/`,
  `docs/`, `assets/`, `schemas/`.
- **Extended CLI.** `ragstrike plugins list | info | enable | disable | validate | reload`. Bare
  `ragstrike plugins` keeps its Phase 3 behaviour.
- **Database migration 2.** `installed_plugins` (first_seen / last_seen / enabled per slug) and
  `plugin_errors` (structured error log with traceback and stage). Plugin statistics are queried
  live off `plugin_results` rather than materialised, because a stale statistics table would
  drift silently.
- **`docs/plugin-development.md`** and **`docs/plugin-lifecycle.md`**.
- 49 new tests (127 total, up from 78).

### Changed — Phase 4

- `plugins/dummy_attack/pack.yaml` → `metadata.yaml`; `attack.py` → `plugin.py`. Class rewritten
  in the declarative style. Full plugin folder layout added (`payloads/`, `tests/`, etc.).
- `AttackMetadata` extended with `tags`, `required_target_type`, `min_framework_version`,
  `license`. Existing fields unchanged.
- `ScanScheduler` calls the extended lifecycle: `healthcheck` → `setup` → `payloads` → `execute`
  → `analyze` → `recommendation` → `cleanup`. Cleanup runs in a `finally` block, always.
- Bumped `PLUGIN_API_VERSION` unchanged (`1.0.0`) — Phase 4 additions are additive on the
  existing contract.

### Added — Phase 3: Core engine

- **`ScanEngine`** — the complete scan lifecycle: authorize → discover plugins → negotiate
  capabilities → plan → execute → collect → store. Contains no attack logic and runs correctly with
  zero plugins installed.
- **`BaseAttack`** with the five-method contract (`metadata`, `payloads`, `execute`, `analyze`,
  `recommendation`), and automatic plugin discovery from directories and entry points. No plugin
  name appears anywhere in the engine, and a test walks its AST to prove it.
- **`BaseTarget` + `FastAPIAdapter`** — configuration-driven request shaping and response
  extraction, so a new bespoke API is a `targets.yaml` change rather than a code change.
- **`ScanScheduler`** — pure planning with capability filtering, then sequential execution with
  per-plugin isolation. Concurrency is designed for and deliberately not implemented.
- **aiosqlite persistence** — `targets`, `scan_sessions`, `plugin_results`, with a forward-only
  migration runner and the effective config snapshot stored on every scan.
- **Typer CLI** — `scan`, `plugins`, `targets`, `version`, with Rich output and distinct exit codes
  so a pipeline can tell a finding from a misconfiguration.
- **Loguru logging** behind the stdlib `logging` API, keeping `ragstrike.logging` (Layer 3) out of
  the engine's import graph.
- `DummyAttack` reference plugin in `plugins/`, and 78 tests covering discovery, configuration,
  scheduling, the engine, the database, and the CLI.

### Changed — Phase 3

- **`.importlinter` contract 1 revised.** The Phase 1 version listed `core`, `scheduler`, and
  `plugins` as siblings on one layer line; import-linter treats same-layer siblings as *independent*,
  which forbade the orchestrator from calling the scheduler and the scheduler from loading plugins —
  making the SDD's own design unimplementable. Layer 2 now spells out the ordering it always had, and
  `core.contracts` sits at Layer 1 beside `models`, which is where SDD §7.2 puts the ports. The rule
  itself is unchanged.
- Logging backend switched from structlog to Loguru, per the Phase 3 stack.
- `ruff` rules `TC001`/`TC002`/`TC003` disabled with a recorded reason: moving annotation-only
  imports into `TYPE_CHECKING` blocks breaks Pydantic and FastAPI, which resolve annotations at
  runtime. That autofix cost real debugging time in the companion repository.

### Added — Phase 0: Architecture

- Complete Software Design Document (`docs/SDD.md`) with four normative annexes
- Twenty Architecture Decision Records covering layering, plugin architecture, the canary-first
  oracle, deterministic scoring, evidence immutability, and the safety model
- Attack pack catalog: twelve categories with OWASP LLM Top 10, MITRE ATLAS, and CWE mapping
- Risk register, development milestones for Phases 1–11, and the post-v1 roadmap

### Added — Phase 1: Engineering Foundation

- Full directory structure for both repositories, every folder documenting its purpose,
  responsibilities, future contents, and explicit boundaries
- Packaging and tool configuration: `pyproject.toml`, `ruff.toml`, `.editorconfig`,
  `.pre-commit-config.yaml`
- **`.importlinter` — the dependency rule as a CI gate**, configured before there is any code capable
  of violating it
- Runtime and development dependency manifests with per-dependency justification
- Configuration scaffold: `.env.example`, `configs/ragstrike.yaml`, `configs/logging.yaml`, scan
  profiles
- Governance documents: README, ARCHITECTURE, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, INSTALL,
  ROADMAP, LICENSE
- GitHub issue templates, pull request template, CODEOWNERS, CI workflow skeleton
- Docker and Compose placeholders

### Not yet implemented

No business logic exists. No RAG, no attacks, no API endpoints, no Streamlit pages, no database CRUD,
no plugin loading. Phase 1 is structure only, by design.

---

## Version history

| Version | Date | Note |
|---|---|---|
| **1.0.0** | 2026-07-30 | First tagged release. Phases 1–15. Two documented gaps: no completed differential run, and 11 pre-existing `mypy` errors |

Pre-1.0 work was carried at `0.1.0`–`0.3.0` and never tagged — the 1.0.0 number was deliberately not
spent before the audit that justified it ([`docs/versioning-policy.md`](docs/versioning-policy.md)).

<!--
Template for future entries:

## [1.0.0] - YYYY-MM-DD

### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security
### Plugin API
  - PLUGIN_API_VERSION x.y.z — what changed and what pack authors must do
-->
