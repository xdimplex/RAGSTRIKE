# Annex A — Complete Directory Structures

*Normative annex to [RAGSTRIKE-SDD-001](SDD.md). Version 1.0.0.*

This annex defines the canonical directory layout for both repositories. Directories are **normative**: implementation phases MUST create them as specified. A module that has no obvious home in this tree is a signal that the design needs an ADR, not that the tree needs an ad-hoc folder.

---

## A.1 Repository 1 — `ragstrike`

```
ragstrike/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                     # lint, types, import-linter, tests, coverage
│   │   ├── security.yml               # bandit, pip-audit, CodeQL, gitleaks
│   │   ├── differential.yml           # nightly VulnerableRAG vs SecureRAG validation
│   │   ├── packs.yml                  # pack conformance suite
│   │   ├── docs.yml                   # MkDocs build + link check
│   │   └── release.yml                # build, publish PyPI, push Docker
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml
│   │   ├── feature_request.yml
│   │   └── attack_pack_proposal.yml
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── CODEOWNERS
│
├── docs/
│   ├── SDD.md                          # THIS design document (source of truth)
│   ├── annex-a-directory-structures.md
│   ├── annex-b-attack-catalog.md
│   ├── annex-c-adrs.md
│   ├── annex-d-risk-roadmap.md
│   ├── architecture/
│   │   ├── overview.md
│   │   ├── layering.md                 # dependency rule + enforcement
│   │   ├── plugin-architecture.md
│   │   ├── analyzer-design.md
│   │   ├── scoring-model.md            # versioned; changelog per model version
│   │   └── diagrams/                   # mermaid sources, exported SVG
│   ├── guides/
│   │   ├── quickstart.md
│   │   ├── configuration.md
│   │   ├── writing-an-attack-pack.md
│   │   ├── writing-a-target-adapter.md
│   │   ├── interpreting-reports.md
│   │   └── ci-integration.md
│   ├── reference/
│   │   ├── api.md                      # REST reference
│   │   ├── cli.md
│   │   ├── manifest-schema.md
│   │   ├── attack-schema.md
│   │   ├── payload-schema.md
│   │   ├── detector-schema.md
│   │   └── database-schema.md
│   ├── policy/
│   │   ├── responsible-use.md
│   │   ├── plugin-trust-model.md
│   │   └── limitations.md              # the "absence of findings ≠ security" statement
│   └── mkdocs.yml
│
├── src/
│   └── ragstrike/
│       ├── __init__.py                 # __version__, PLUGIN_API_VERSION
│       ├── __main__.py                 # `python -m ragstrike`
│       │
│       ├── core/                       # LAYERS 1 & 2 — no infrastructure imports
│       │   ├── domain/                 # Layer 1
│       │   │   ├── entities/
│       │   │   │   ├── target.py
│       │   │   │   ├── authorization.py
│       │   │   │   ├── scan.py
│       │   │   │   ├── attack_case.py
│       │   │   │   ├── probe.py
│       │   │   │   ├── signal.py
│       │   │   │   ├── finding.py
│       │   │   │   ├── recommendation.py
│       │   │   │   ├── canary.py
│       │   │   │   └── report.py
│       │   │   ├── values/
│       │   │   │   ├── severity.py
│       │   │   │   ├── confidence.py
│       │   │   │   ├── risk_score.py
│       │   │   │   ├── posture_grade.py
│       │   │   │   ├── capability.py
│       │   │   │   ├── impact_class.py
│       │   │   │   └── identifiers.py
│       │   │   ├── states/
│       │   │   │   ├── scan_state.py       # state machine + legal transitions
│       │   │   │   └── case_state.py
│       │   │   └── errors.py               # RAGStrikeError taxonomy
│       │   │
│       │   ├── contracts/              # Layer 1 — ports (protocols only)
│       │   │   ├── target_adapter.py
│       │   │   ├── capability_protocols.py # SupportsChat, SupportsIngest, ...
│       │   │   ├── attack_plugin.py
│       │   │   ├── detector.py
│       │   │   ├── payload_source.py
│       │   │   ├── mutator.py
│       │   │   ├── renderer.py
│       │   │   ├── repositories.py
│       │   │   └── event_bus.py
│       │   │
│       │   ├── config/                 # Layer 2
│       │   │   ├── models.py               # Pydantic settings schema
│       │   │   ├── loader.py               # layered merge + precedence
│       │   │   ├── validation.py           # fail-fast checks
│       │   │   └── defaults.py
│       │   │
│       │   ├── registry/               # Layer 2
│       │   │   ├── plugin_registry.py      # discovery policy, compat, activation
│       │   │   ├── adapter_registry.py
│       │   │   ├── detector_registry.py
│       │   │   ├── renderer_registry.py
│       │   │   ├── compatibility.py        # SemVer range resolution
│       │   │   └── health.py               # plugin health reporting
│       │   │
│       │   ├── scheduler/              # Layer 2 — PURE, no I/O
│       │   │   ├── planner.py              # expansion pipeline
│       │   │   ├── capability_filter.py
│       │   │   ├── variant_expander.py     # payload × variables × mutators
│       │   │   ├── budget.py               # caps + explicit truncation logging
│       │   │   ├── ordering.py             # seeded shuffle + topological sort
│       │   │   └── plan.py                 # immutable ScanPlan
│       │   │
│       │   ├── executor/               # Layer 2
│       │   │   ├── engine.py               # TaskGroup driver
│       │   │   ├── concurrency.py          # semaphore
│       │   │   ├── rate_limiter.py         # token bucket (non-disableable)
│       │   │   ├── retry.py                # backoff + jitter policy
│       │   │   ├── isolation.py            # per-case exception guard
│       │   │   ├── session.py              # fresh-session semantics
│       │   │   └── cancellation.py
│       │   │
│       │   ├── evidence/               # Layer 2
│       │   │   ├── recorder.py             # immutable probe creation
│       │   │   ├── canary_mint.py          # token generation + registry
│       │   │   ├── cleanup.py              # target artifact removal + residual tracking
│       │   │   └── redaction.py            # egress redaction policy
│       │   │
│       │   ├── analyzer/               # Layer 2
│       │   │   ├── engine.py               # ensemble runner
│       │   │   ├── aggregation.py          # weighted noisy-OR, span dedup
│       │   │   ├── verdict.py
│       │   │   └── detectors/              # BUILT-IN detectors (packs may add more)
│       │   │       ├── canary.py
│       │   │       ├── pattern.py
│       │   │       ├── secret_patterns.py  # curated regex library + entropy gate
│       │   │       ├── pii_patterns.py
│       │   │       ├── similarity.py
│       │   │       ├── refusal_absence.py
│       │   │       ├── structural.py
│       │   │       ├── retrieval_integrity.py
│       │   │       ├── citation_verifier.py
│       │   │       ├── differential.py
│       │   │       ├── threshold.py
│       │   │       └── llm_judge.py        # optional, confidence-capped
│       │   │
│       │   ├── scoring/                # Layer 2 — PURE arithmetic
│       │   │   ├── finding_score.py        # F = 10 · I · E · C
│       │   │   ├── aggregation.py          # per-category max → noisy-OR → density
│       │   │   ├── severity.py             # band mapping
│       │   │   ├── grade.py                # posture grade
│       │   │   ├── coverage.py             # coverage fraction + qualifier
│       │   │   └── models/
│       │   │       └── v1_0_0.py           # versioned weight tables
│       │   │
│       │   ├── recommendations/        # Layer 2
│       │   │   ├── catalog.py              # load + validate YAML catalog
│       │   │   ├── matcher.py              # finding → entries
│       │   │   └── prioritizer.py          # risk reduced per unit effort
│       │   │
│       │   ├── reporting/              # Layer 2
│       │   │   ├── model.py                # format-independent ReportModel
│       │   │   ├── builder.py              # assemble all 10 sections
│       │   │   ├── sections/
│       │   │   │   ├── executive_summary.py
│       │   │   │   ├── target_info.py
│       │   │   │   ├── scan_metadata.py
│       │   │   │   ├── coverage.py
│       │   │   │   ├── findings.py
│       │   │   │   ├── evidence.py
│       │   │   │   ├── risk_analysis.py
│       │   │   │   ├── remediation.py
│       │   │   │   ├── owasp_mapping.py
│       │   │   │   └── appendix.py
│       │   │   └── strings/                # localization-ready catalog (NFR-14)
│       │   │       └── en.yaml
│       │   │
│       │   ├── events/                 # Layer 2
│       │   │   ├── bus.py
│       │   │   ├── types.py                # scan.*, case.*, finding.*
│       │   │   └── throttle.py
│       │   │
│       │   └── orchestrator/           # Layer 2 — the single use case
│       │       ├── scan_orchestrator.py    # run_scan()
│       │       ├── commands.py             # RunScanCommand, CancelScanCommand
│       │       ├── state_machine.py        # scan transitions
│       │       └── reconciler.py           # orphaned-scan recovery on startup
│       │
│       ├── infrastructure/             # LAYER 3 — replaceable implementations
│       │   ├── database/
│       │   │   ├── connection.py           # aiosqlite pool, pragmas
│       │   │   ├── migrations/
│       │   │   │   ├── runner.py           # checksum-verified, forward-only
│       │   │   │   ├── 0001_initial.sql
│       │   │   │   ├── 0002_canaries.sql
│       │   │   │   └── ...
│       │   │   ├── repositories/
│       │   │   │   ├── target_repository.py
│       │   │   │   ├── scan_repository.py
│       │   │   │   ├── case_repository.py
│       │   │   │   ├── probe_repository.py     # NO update/delete methods
│       │   │   │   ├── signal_repository.py
│       │   │   │   ├── finding_repository.py
│       │   │   │   ├── canary_repository.py
│       │   │   │   └── report_repository.py
│       │   │   ├── mappers.py              # row ↔ domain entity
│       │   │   └── retention.py            # compaction of old scans
│       │   │
│       │   ├── targets/                # concrete adapters
│       │   │   ├── http_adapter.py         # JSONPath-configurable
│       │   │   ├── local_python_adapter.py
│       │   │   ├── openai_compatible_adapter.py
│       │   │   ├── ollama_adapter.py
│       │   │   ├── langchain_adapter.py
│       │   │   ├── llamaindex_adapter.py
│       │   │   └── mapping.py              # request/response JSONPath mapping
│       │   │
│       │   ├── llm/                    # OPTIONAL — judge detector only
│       │   │   ├── provider.py             # abstract client
│       │   │   ├── ollama_client.py
│       │   │   └── structured_output.py    # forced schema, temperature 0
│       │   │
│       │   ├── renderers/
│       │   │   ├── html_renderer.py
│       │   │   ├── json_renderer.py
│       │   │   ├── pdf_renderer.py         # Phase 11+
│       │   │   └── templates/
│       │   │       ├── report.html.j2
│       │   │       ├── partials/
│       │   │       └── assets/             # inlined CSS; no external requests
│       │   │
│       │   ├── plugins/
│       │   │   ├── entry_point_discovery.py
│       │   │   ├── directory_discovery.py
│       │   │   ├── manifest_parser.py      # parses WITHOUT importing pack code
│       │   │   └── loader.py               # lazy module import
│       │   │
│       │   ├── templating/
│       │   │   └── safe_renderer.py        # non-evaluating payload templates
│       │   │
│       │   └── filesystem/
│       │       ├── report_writer.py
│       │       └── paths.py
│       │
│       ├── attacks/                    # FIRST-PARTY PACKS
│       │   │                           # registered via the SAME public entry points
│       │   │                           # third parties use (dogfooding SC2)
│       │   ├── prompt_injection/
│       │   │   ├── pack.yaml
│       │   │   ├── attacks/
│       │   │   ├── payloads/
│       │   │   ├── detectors/
│       │   │   └── recommendations/
│       │   ├── indirect_prompt_injection/
│       │   ├── prompt_leakage/
│       │   ├── role_override/
│       │   ├── context_injection/
│       │   ├── context_poisoning/
│       │   ├── secret_extraction/
│       │   ├── pii_leakage/
│       │   ├── context_window_overflow/
│       │   ├── hallucination_evaluation/
│       │   ├── retrieval_integrity/
│       │   └── citation_verification/
│       │
│       ├── sdk/                        # ATTACK SDK — Phase 5
│       │   ├── base/
│       │   │   ├── attack.py
│       │   │   ├── detector.py
│       │   │   └── mutator.py
│       │   ├── testing/
│       │   │   ├── fake_target.py
│       │   │   ├── echo_target.py
│       │   │   ├── refusing_target.py
│       │   │   ├── leaky_target.py
│       │   │   ├── flaky_target.py
│       │   │   └── slow_target.py
│       │   ├── conformance/
│       │   │   ├── pack_conformance.py
│       │   │   ├── adapter_conformance.py  # LSP enforcement
│       │   │   └── detector_purity.py
│       │   ├── validation/
│       │   │   ├── schemas/                # JSON Schema for every YAML contract
│       │   │   └── validators.py
│       │   ├── replay/
│       │   │   └── harness.py              # re-analyze stored evidence offline
│       │   └── scaffold/
│       │       └── templates/              # `ragstrike sdk new-pack`
│       │
│       ├── api/                        # LAYER 4
│       │   ├── app.py                      # FastAPI factory
│       │   ├── dependencies.py             # DI wiring / composition root
│       │   ├── errors.py                   # exception → HTTP envelope table
│       │   ├── middleware/
│       │   │   ├── correlation_id.py
│       │   │   └── request_logging.py
│       │   ├── routers/
│       │   │   ├── health.py
│       │   │   ├── version.py
│       │   │   ├── targets.py
│       │   │   ├── packs.py
│       │   │   ├── profiles.py
│       │   │   ├── scans.py
│       │   │   ├── findings.py
│       │   │   ├── reports.py
│       │   │   ├── compare.py
│       │   │   └── recommendations.py
│       │   ├── schemas/                    # Pydantic request/response models
│       │   └── streaming/
│       │       └── sse.py
│       │
│       ├── cli/                        # LAYER 4
│       │   ├── main.py                     # Typer app
│       │   ├── commands/
│       │   │   ├── doctor.py
│       │   │   ├── targets.py
│       │   │   ├── packs.py
│       │   │   ├── scan.py
│       │   │   ├── scans.py
│       │   │   ├── report.py
│       │   │   ├── compare.py
│       │   │   ├── replay.py
│       │   │   └── sdk.py
│       │   ├── output/
│       │   │   ├── human.py                # Rich rendering
│       │   │   └── json_out.py
│       │   └── exit_codes.py
│       │
│       ├── dashboard/                  # LAYER 4 — MUST NOT import core.*
│       │   ├── app.py
│       │   ├── api_client.py               # the ONLY way it reaches the engine
│       │   ├── pages/
│       │   │   ├── 1_dashboard.py
│       │   │   ├── 2_targets.py
│       │   │   ├── 3_new_scan.py
│       │   │   ├── 4_live_scan.py
│       │   │   ├── 5_results.py
│       │   │   ├── 6_history.py
│       │   │   └── 7_settings.py
│       │   ├── components/
│       │   │   ├── grade_badge.py
│       │   │   ├── findings_table.py
│       │   │   ├── evidence_viewer.py      # highlighted matched spans
│       │   │   ├── coverage_panel.py
│       │   │   └── plugin_health.py
│       │   └── state.py
│       │
│       └── logging/
│           ├── setup.py                    # structlog configuration
│           ├── processors.py               # redaction processor in the pipeline
│           └── context.py                  # correlation binding
│
├── configs/
│   ├── ragstrike.yaml                      # installation defaults
│   ├── profiles/
│   │   ├── quick.yaml
│   │   ├── standard.yaml
│   │   └── deep.yaml
│   ├── targets/
│   │   ├── vulnerable-rag.example.yaml
│   │   └── secure-rag.example.yaml
│   ├── scoring/
│   │   └── v1_0_0.yaml                     # weight tables (versioned)
│   └── recommendations/
│       └── catalog.yaml                    # core remediation catalog
│
├── packs/                                  # local (non-pip) pack drop-in dir
│   └── .gitkeep
│
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   ├── scheduler/
│   │   ├── scoring/
│   │   ├── analyzer/
│   │   ├── config/
│   │   └── registry/
│   ├── contract/
│   │   ├── test_adapter_conformance.py
│   │   └── test_pack_conformance.py
│   ├── integration/
│   │   ├── test_orchestrator_pipeline.py
│   │   ├── test_repositories.py
│   │   ├── test_api.py
│   │   └── test_plugin_loading.py
│   ├── golden/
│   │   ├── evidence_corpus/                # recorded real responses
│   │   └── test_analyzer_replay.py
│   ├── system/
│   │   ├── test_differential.py            # SC1 keystone test
│   │   └── test_determinism.py             # SC4
│   ├── property/
│   │   └── test_scoring_properties.py
│   ├── extensibility/
│   │   ├── fixture_pack/                   # installed at test time
│   │   └── test_zero_core_edit.py          # SC2
│   ├── fixtures/
│   └── conftest.py
│
├── examples/
│   ├── ci_integration/
│   │   ├── github_action.yml
│   │   └── gitlab_ci.yml
│   ├── custom_adapter/
│   ├── custom_pack/
│   └── notebooks/
│
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.dashboard
│   ├── docker-compose.yml
│   ├── docker-compose.lab.yml              # + VulnerableRAG + SecureRAG + Ollama
│   └── entrypoint.sh
│
├── scripts/
│   ├── bootstrap_dev.sh / .ps1
│   ├── validate_manifests.py
│   └── regenerate_diagrams.py
│
├── data/                                   # gitignored — scans.db lives here
│   └── .gitkeep
├── reports/                                # gitignored — rendered artifacts
│   └── .gitkeep
│
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── .importlinter                           # dependency-rule contracts
├── .pre-commit-config.yaml
├── .gitignore                              # data/, reports/, *.db, .env
├── .env.example
├── LICENSE                                 # Apache-2.0
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
└── SECURITY.md
```

### A.1.1 Directory Responsibility Summary

| Path | Owns | Forbidden |
|---|---|---|
| `core/domain` | Business vocabulary and invariants | Any import outside stdlib/typing |
| `core/contracts` | Port definitions | Any logic |
| `core/scheduler` | Deciding *what* to run | Any I/O |
| `core/executor` | *Performing* the run | Interpreting responses |
| `core/analyzer` | Judging responses | Knowing about transport or storage |
| `core/scoring` | Arithmetic | I/O, LLM calls (enforced by import-linter) |
| `core/reporting` | Content assembly | Format-specific markup |
| `infrastructure/*` | All technology choices | Being imported by `core/*` |
| `attacks/*` | First-party packs | Importing private core internals |
| `sdk/*` | Third-party developer experience | Being a runtime dependency of `core/*` |
| `api`, `cli` | Delivery | Business logic |
| `dashboard` | Presentation | Importing `core/*` or `infrastructure/*` |

---

## A.2 Repository 2 — `vulnerable-rag` (VulnerableRAG + SecureRAG)

Per **ADR-009**, both applications share one codebase and differ only in the composition of the `SecurityPolicy` chain.

```
vulnerable-rag/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── docker.yml
│       └── lab-smoke.yml               # both profiles boot, ingest, answer
│
├── docs/
│   ├── README.md
│   ├── LAB_SAFETY.md                   # containment rules, why loopback-only
│   ├── vulnerabilities.md              # V1–V9 catalogue with reproduction steps
│   ├── defenses.md                     # the SecureRAG control set
│   ├── the-diff.md                     # side-by-side: the executable remediation guide
│   └── teaching-guide.md               # exercises for learners
│
├── packages/
│   └── ragcore/                        # SHARED — identical for both profiles
│       ├── __init__.py
│       ├── domain/
│       │   ├── document.py
│       │   ├── chunk.py
│       │   ├── query.py
│       │   └── answer.py
│       ├── ingestion/
│       │   ├── loaders/
│       │   │   └── pdf_loader.py
│       │   ├── chunker.py
│       │   ├── embedder.py
│       │   └── pipeline.py             # load → extract → chunk → embed → store
│       ├── retrieval/
│       │   ├── vector_store.py         # ChromaDB client
│       │   ├── retriever.py
│       │   └── reranker.py
│       ├── generation/
│       │   ├── prompt_builder.py       # consumes the active template
│       │   ├── llm_client.py           # Ollama / Qwen3
│       │   └── pipeline.py             # embed → retrieve → assemble → generate → post
│       ├── policy/                     # ★ THE SEAM ★
│       │   ├── protocol.py             # SecurityPolicy interface
│       │   ├── chain.py                # ordered policy composition
│       │   ├── hooks.py                # on_ingest, on_chunk, on_context_assembly,
│       │   │                           # on_prompt_build, on_response
│       │   └── controls/               # implementations — used ONLY by secure profile
│       │       ├── context_sanitizer.py
│       │       ├── unicode_normalizer.py
│       │       ├── instruction_neutralizer.py
│       │       ├── output_filter.py
│       │       ├── secret_masker.py
│       │       ├── pii_masker.py
│       │       ├── input_validator.py
│       │       ├── retrieval_filter.py
│       │       ├── session_bounder.py
│       │       └── citation_grounder.py
│       ├── session/
│       │   └── memory.py               # bounding is a policy, not a core behaviour
│       ├── api/
│       │   ├── app_factory.py          # builds an app from a profile
│       │   ├── routers/
│       │   │   ├── chat.py
│       │   │   ├── upload.py
│       │   │   ├── sources.py
│       │   │   ├── chunks.py           # exposes retrieval internals for testing
│       │   │   └── health.py
│       │   └── schemas/
│       ├── ui/
│       │   ├── app_factory.py
│       │   ├── pages/
│       │   │   ├── chat.py
│       │   │   ├── upload.py
│       │   │   ├── corpus.py
│       │   │   └── retrieval_inspector.py
│       │   └── components/
│       └── config/
│           ├── models.py
│           └── loader.py
│
├── apps/
│   ├── vulnerable/                     # VulnerableRAG — port 9000 / UI 8601
│   │   ├── main_api.py
│   │   ├── main_ui.py
│   │   ├── profile.py                  # SecurityPolicyChain([])  ← empty BY CONSTRUCTION
│   │   ├── prompts/
│   │   │   └── system_prompt.txt       # weak template + SYNTHETIC canary-tagged secrets
│   │   └── config.yaml
│   │
│   └── secure/                         # SecureRAG — port 9001 / UI 8602
│       ├── main_api.py
│       ├── main_ui.py
│       ├── profile.py                  # SecurityPolicyChain([...full control set...])
│       ├── prompts/
│       │   └── system_prompt.txt       # structured, delimited, no secrets
│       └── config.yaml
│
├── corpus/                             # IDENTICAL for both profiles
│   ├── benign/
│   │   ├── company_handbook.pdf
│   │   ├── product_faq.pdf
│   │   └── policy_document.pdf
│   ├── poisoned/                       # pre-staged attack documents for teaching
│   │   ├── README.md                   # explains each document's payload
│   │   ├── hidden_instruction.pdf
│   │   ├── zero_width_injection.pdf
│   │   └── fake_authority_memo.pdf
│   └── manifest.yaml                   # provenance — enables retrieval-integrity checks
│
├── tests/
│   ├── unit/
│   ├── integration/
│   │   ├── test_ingestion.py
│   │   └── test_query_pipeline.py
│   ├── parity/
│   │   └── test_functional_parity.py   # ★ both profiles answer benign queries
│   │                                   #   identically — proves the ONLY difference
│   │                                   #   is security controls (protects SC1)
│   └── policy/
│       └── test_controls.py
│
├── docker/
│   ├── Dockerfile.vulnerable
│   ├── Dockerfile.secure
│   ├── docker-compose.yml              # binds 127.0.0.1 ONLY
│   └── ollama-init.sh                  # pulls qwen3
│
├── scripts/
│   ├── seed_corpus.py
│   └── reset_lab.py
│
├── data/                               # gitignored — chroma/ lives here
│   └── .gitkeep
│
├── pyproject.toml
├── requirements.txt
├── .gitignore
├── .env.example
├── LICENSE
├── README.md                           # prominent DO-NOT-DEPLOY warning
└── SECURITY.md
```

### A.2.1 Two Structural Guarantees

**1. The empty chain is structural, not configurational.** `apps/vulnerable/profile.py` constructs `SecurityPolicyChain([])` in code. There is no configuration flag that could accidentally enable a control on the vulnerable profile — because if one ever did, every scan result validating RAGStrike would silently become meaningless while continuing to look correct.

**2. Functional parity is tested.** `tests/parity/test_functional_parity.py` asserts that both profiles return substantively equivalent answers to a fixed set of benign queries over the same corpus. This is what makes the differential test (SC1) a measurement of *security controls* rather than of incidental behavioural drift.

---

## A.3 Cross-Repository Conventions

| Convention | Both repositories |
|---|---|
| Source layout | `src/` layout in `ragstrike`; `packages/` + `apps/` in `vulnerable-rag`. Never flat. |
| Config | All runtime configuration in YAML under `configs/` or `apps/*/config.yaml`. No configuration in code beyond typed defaults. |
| Secrets | `.env.example` committed; `.env` gitignored; lab secrets synthetic and canary-tagged. |
| Generated data | `data/` and `reports/` gitignored in both. |
| Diagrams | Mermaid sources live beside the docs that use them; exports are generated, never hand-edited. |
| Tests | Mirror the source tree; one test module per source module for unit tiers. |
