# `analyzers` — Analyzer Engine

> **SDD reference:** [SDD §16](../../../docs/SDD.md), [ADR-011](../../../docs/annex-c-adrs.md), [ADR-012](../../../docs/annex-c-adrs.md)
> **Full documentation:** [`docs/analyzer-engine.md`](../../../docs/analyzer-engine.md)
> **Phase:** 10 · **Status:** implemented.

## Purpose

Converts raw plugin execution results into standardized security findings.

**The analyzer, not the plugin, decides.** A plugin reports what it observed; this engine decides
what that means, using configurable rules. Status, severity, confidence, and risk are all re-derived
in one place against one rule set — which is what makes findings comparable across packs, and what
lets an operator re-tune grading without editing a plugin.

## Why no plugin needed changing

`Observation` is *derived from* a plugin's existing `PluginResult`. A plugin's own verdict arrives as
`reported_status` — an observation about what the plugin concluded, not the finding's status. Rules
may agree with it, sharpen it, or overrule it.

The proof it is real: a plugin reporting `FAIL` with no evidence is graded `INCONCLUSIVE`, with the
disagreement recorded in `metadata.overrode_plugin`.

## Layout

```
analyzers/
├── base/              Finding, Observation, BaseAnalyzer, ports
├── rules/             RuleEngine — configurable, data not code
├── scoring/           ScoreEngine — finding, category, scan
├── confidence/        ConfidenceEngine — numeric and banded
├── evidence/          EvidenceEngine — one shape from many
├── recommendations/   RecommendationEngine — retrieved, never generated
├── registry/          AnalyzerRegistry — discovery without engine changes
├── validators/        ValidationEngine — loud rejection
├── utils/             small shared helpers
├── engine.py          AnalyzerEngine + StandardAnalyzer + AnalysisReport
├── config.py          builds an engine from configs/analyzer/
└── detectors/         Phase 1 scaffold, unused by this phase
```

> **Tests live in `tests/unit/` and `tests/integration/`**, not inside this package. `pytest`
> collects from the repository's `tests/` tree (`testpaths` in `pyproject.toml`), so tests placed
> under `src/` would never run.

## Pipeline

```
validate → normalize evidence → apply rules → confidence → risk → recommend → Finding
```

Each engine has one responsibility, so re-tuning scoring cannot break evidence handling.

## Layer position

Below `database`, above `plugins`. That direction is deliberate: analysis is a pure transformation,
so the engine declares a `FindingRepository` port and the database layer implements it. Depending on
SQLite would mean the whole engine could only be tested with a database attached.

## This folder must NEVER contain

- An import of `ragstrike.database`. Persistence is a port the caller supplies, and `lint-imports`
  enforces the direction.
- An import of any pack or plugin, or a plugin name as a code-level string literal. Rules may name
  categories — that is configuration, not code.
- A hardcoded severity, weight, or threshold. Everything tunable lives in `configs/analyzer/`.
- A model call anywhere in scoring. Every number comes from a published formula (ADR-011).
- A detector with hidden state or wall-clock dependence — purity is what makes offline re-analysis
  work.
