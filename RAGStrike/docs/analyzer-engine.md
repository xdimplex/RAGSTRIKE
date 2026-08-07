# Analyzer Engine

Converts raw plugin execution results into standardized security findings.

**The analyzer, not the plugin, decides.** A plugin reports what it observed; the engine decides what
that means, using configurable rules. Every rating on a finding — status, severity, confidence, risk
— is re-derived in one place against one rule set.

That matters because a plugin's own verdict is written by whoever wrote the plugin. Two packs might
both call something HIGH while meaning different things by it. Grading everything against one table
in one file is what makes findings comparable across packs, and what lets an operator re-tune
severity without editing a single plugin.

---

## Architecture

```mermaid
flowchart TD
    PR[PluginResult<br/><i>what the plugin observed</i>] --> OBS[Observation]
    OBS --> VAL[ValidationEngine]
    VAL -->|rejected| REJ[recorded on the report]
    VAL -->|accepted| EV[EvidenceEngine<br/><i>normalize</i>]
    EV --> RULE[RuleEngine<br/><i>status + severity</i>]
    RULE --> CONF[ConfidenceEngine]
    CONF --> SCORE[ScoreEngine<br/><i>risk</i>]
    SCORE --> REC[RecommendationEngine]
    REC --> F[Finding]
    F --> REPO[(findings table)]
    F --> RPT[AnalysisReport<br/><i>for the Reporting Engine</i>]
```

Each engine has one responsibility, so re-tuning scoring cannot break evidence handling and a new
rule type touches only the rule engine.

### Class model

```mermaid
classDiagram
    class Observation {
        +plugin_id: str
        +category: str
        +reported_status: PluginOutcome
        +evidence: dict
        +failure_ratio: float
        +from_plugin_result(result)
    }
    class Finding {
        +id, scan_id, plugin_id, category
        +status: PluginOutcome
        +severity: Severity
        +confidence, confidence_band
        +risk_score: float
        +evidence, recommendation, references
        +notes, analyzer_version, timestamp
    }
    class BaseAnalyzer {
        <<abstract>>
        +name: str
        +handles: tuple
        +analyze(observation) Finding
    }
    class StandardAnalyzer
    class AnalyzerEngine {
        +analyze(observations) AnalysisReport
        +analyze_and_store(observations, repo)
    }
    class AnalyzerRegistry {
        +register(analyzer)
        +for_category(category)
    }
    class FindingRepository {
        <<interface>>
        +add_findings(findings)
        +findings_for(scan_id)
    }

    BaseAnalyzer <|-- StandardAnalyzer
    AnalyzerEngine --> AnalyzerRegistry
    AnalyzerEngine --> BaseAnalyzer
    AnalyzerEngine ..> FindingRepository : port
    StandardAnalyzer --> Observation
    StandardAnalyzer --> Finding
```

### Sequence

```mermaid
sequenceDiagram
    participant C as Caller
    participant E as AnalyzerEngine
    participant V as ValidationEngine
    participant A as StandardAnalyzer
    participant R as RuleEngine
    participant Repo as FindingRepository

    C->>E: analyze_and_store(observations, repo)
    E->>V: validate_all(observations)
    V-->>E: accepted, rejected
    loop each accepted
        E->>A: analyze(observation)
        A->>A: normalize evidence
        A->>R: evaluate(observation)
        R-->>A: status, severity, modifier, matched rules
        A->>A: confidence -> risk -> recommendation
        A-->>E: Finding
    end
    E->>E: score_scan(findings)
    E->>Repo: add_findings(findings)
    E-->>C: AnalysisReport
```

---

## Why the engine needs no plugin changes

The Phase 10 brief asks that plugins return raw execution results only, and simultaneously that no
plugin change be required. Both hold because of one type:

**`Observation` is derived from a plugin's existing `PluginResult`.** A plugin's own verdict arrives
as `reported_status` — a field named to make its status obvious. It is *an observation about what the
plugin concluded*, not the finding's status. The rule engine may agree with it, sharpen it, or
overrule it.

The proof that this is real rather than cosmetic: a plugin reporting `FAIL` with no evidence recorded
is graded `INCONCLUSIVE`, and the disagreement is recorded on the finding.

```python
finding.status                              # INCONCLUSIVE  (the analyzer's verdict)
finding.metadata["plugin_reported_status"]  # FAIL          (what the plugin said)
finding.metadata["overrode_plugin"]         # True
```

Three tests enforce the independence structurally: no pack imports the analyzer, the analyzer imports
no pack, and the analyzer contains no plugin name as a code-level string literal.

---

## Finding model

| Field | Meaning |
|---|---|
| `id` | Unique identifier |
| `scan_id` | The scan it belongs to |
| `plugin_id` | Provenance — which plugin's observations it came from, not who decided |
| `category` | Groups findings; selects category-scoped rules and advice |
| `status` | `PASS` / `FAIL` / `INCONCLUSIVE`, decided by rules. `ERROR` and `SKIPPED` survive from the observation because they describe the *run*, not the target |
| `severity` | Assigned by rules, never copied from the plugin |
| `confidence` | `0.0`–`1.0` |
| `confidence_band` | `low` / `medium` / `high` — the same number, bucketed |
| `risk_score` | `0.0`–`10.0`, deterministic arithmetic |
| `evidence` | Normalized to one shape |
| `recommendation` | Retrieved, never generated |
| `references` | From the recommendation mapping |
| `timestamp` | When the analyzer produced it |
| `notes` | Which rules fired, and what the plugin originally said |
| `analyzer_version` | A finding is only interpretable against the logic that produced it |
| `metadata` | Matched rules, confidence components, original plugin outcome |

`is_vulnerability` is `FAIL` only. `INCONCLUSIVE` is excluded deliberately: an undetermined result is
not evidence of weakness any more than of strength.

---

## Evidence model

Every pack records evidence differently — the injection pack writes detector signals, the leakage
pack writes redacted response summaries, the poisoning pack writes retrieved sources and chunk ids. A
report that has to understand three shapes will understand two and quietly mishandle the third.

```
NormalizedEvidence
├── summary       one-line description
├── text          observed response (already redacted by the pack, if it redacts)
├── signals       detector signals, flattened across cases
├── sources       retrieved or cited sources, deduplicated in first-seen order
├── chunk_ids     retrieved chunk identifiers
├── cases         per-case results
├── timing        execution_ms, payloads_executed
├── structured    everything else, verbatim
└── attachments   reserved — always empty today
```

**Normalization never invents.** A section absent from the input is absent from the output, not
defaulted to something plausible. An empty `sources` means the plugin reported none — a fact worth
preserving, and quite different from "this plugin does not deal in sources".

Source keys are translated (`retrieved_sources` / `sources` / `citations`) because the packs were
written independently. That is a translation table, not a spec.

---

## Rule engine

**Rules are data, never code.** A condition is a field/operator/value triple the engine interprets.
Nothing is `eval`'d and no attribute is traversed by name from config — a rules file is untrusted
input, and a configuration format that can execute is a bad trade for a security tool (ADR-016).

```yaml
rules:
  - id: injection-highly-reliable
    description: "More than half the payloads succeeded."
    priority: 75
    applies_to: [prompt_injection, prompt_leakage]
    conditions:
      - {field: reported_status, operator: eq, value: FAIL}
      - {field: failure_ratio, operator: gt, value: 0.5}
    status: FAIL
    severity: CRITICAL
    confidence_modifier: 0.1
```

**Fields:** `plugin_id`, `category`, `reported_status`, `reported_confidence`, `execution_ms`,
`payloads_executed`, `total_cases`, `failed_cases`, `failure_ratio`, `has_error`, `has_evidence`,
`target`.

The fact table is flat and explicit rather than allowing dotted paths into arbitrary structures. A
rules file that can traverse anything becomes coupled to every pack's internal evidence shape, and
then no pack can change its evidence without breaking somebody's rules.

**Operators:** `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `contains`, `exists`.

**First match wins, by descending priority.** Accumulating every match would make the verdict depend
on file order in ways nobody could predict from reading one rule. Set `stop: false` to continue.

**Conditions are ANDed.** An OR is two rules, which reads better than nested boolean config.

### Failure modes, and what they degrade to

| Problem | Behaviour |
|---|---|
| Malformed rule | Skipped, named in `RuleSet.skipped`. One bad rule must not disable grading. |
| Unknown operator | Rule refused at load — a rule that never matches is indistinguishable from "the target is fine". |
| Missing file | Empty ruleset; the engine falls back to the plugin's reported status. |
| No rule matches | Plugin status stands, severity falls back to `default_severity`. |

The fallback is deliberate: an empty rules file must still produce usable findings, so the engine
degrades to "trust the plugin" rather than to "no finding".

---

## Scoring

**Every number comes from a published formula over recorded fields (ADR-011).** No model call. A
reader can reproduce any score by hand.

```
finding  = severity_weight × confidence        (0 unless the finding is a FAIL)
category = worst finding + (additional failures × volume_factor), capped at 10
scan     = weighted mean of category scores
```

Three choices worth explaining:

**Multiplying by confidence.** A critical finding nobody is sure of should not outrank a
high-severity one that is certain.

**Only `FAIL` contributes.** A `PASS` found nothing; an `INCONCLUSIVE` established nothing. Letting
either contribute would produce a risk number partly composed of things nobody observed.

**A mean, not a max, for the scan.** One broken category among ten is a different situation from ten
broken categories, and a max cannot tell them apart.

A category absent from `category_weights` weighs 1.0, so a new pack contributes the day it ships
rather than scoring zero until someone remembers to add it.

---

## Confidence

Confidence answers *how much should a reader trust this finding* — a different question from severity
(*how bad is it if true*). Conflating them produces reports where a certain-but-minor issue outranks
a probable-but-critical one.

```
score = plugin_confidence × 0.5
      + 0.3 if any evidence recorded
      + min(signals, 3)/3 × 0.2
      − 0.3 if no evidence
      − 0.2 if the run errored
      + rule modifiers
      → clamped to 0.0–1.0
```

**The judgement encoded in the defaults: evidence matters more than a plugin's self-assessment.** A
plugin claiming 0.9 with nothing recorded is trusted less than one claiming 0.6 that shows its
working, because the second can be checked.

Corroboration is capped: ten detectors agreeing is not meaningfully more convincing than three, and
without a ceiling a noisy pack would outrank a careful one on volume alone.

Bands: `high` ≥ 0.75, `medium` ≥ 0.4, else `low`. Every component is returned alongside the score —
a number a reader cannot decompose is one they cannot argue with.

---

## Recommendations

**Retrieved, never generated (ADR-012).** A model composing remediation would produce text that
differs between identical runs and that nobody reviewed before it reached an operator.

Lookup order, most specific first: **plugin → category → severity → default.**

A pack's own recommendation wins over all of them. The packs know their failure modes better than a
severity-keyed default ever could; this engine fills the gap for plugins that ship none, and gives an
operator one file to override all of them from.

---

## Persistence

`findings` is a separate table from `plugin_results`, added by migration 3.

| Table | Records | Written by |
|---|---|---|
| `plugin_results` | What a plugin **observed** | The scheduler |
| `findings` | What the analyzer **concluded**, against a versioned rule set | The analyzer |

Keeping them separate is what makes re-analysis possible: rules change, so the same stored
observations can be re-graded later and produce a second, differently-versioned finding without
rewriting the record of what actually happened.

**The engine cannot import the database.** `analyzers` sits below `database` in the layer contract,
so the engine declares a `FindingRepository` port and `database/repositories/` implements it. That is
the right direction — analysis is a pure transformation, and making it depend on SQLite would mean
the whole engine could only be tested with a database attached. `lint-imports` enforces it.

---

## Configuration guide

Five files in `configs/analyzer/`:

| File | Controls |
|---|---|
| `analyzer.yaml` | Points at the other four; analyzer version; strict validation |
| `rules.yaml` | Status and severity assignment |
| `scoring.yaml` | Severity weights, volume factor, category weights, model version |
| `confidence.yaml` | Weights, penalties, corroboration cap, band thresholds |
| `recommendations.yaml` | Advice by plugin, category, and severity |

```python
from ragstrike.analyzers.config import build_engine

engine, report = build_engine()          # defaults to configs/analyzer
if not report.fully_configured:
    print(report.missing, report.skipped_rules)
```

**Every loader falls back to built-in defaults, and reports what fell back.** A security tool that
refuses to analyze because one YAML file has a typo is one that does not get run — but a tool that
silently ignores the file an operator just edited is worse, so fallbacks are recorded rather than
hidden.

Relative paths in `analyzer.yaml` resolve against the config directory; absolute paths let
site-specific rules live outside the distribution and survive upgrades.

---

## Reporting interface

`AnalysisReport` is the interface for the future Reporting Engine. **Structured objects only** — no
HTML, no PDF, no formatting decisions. A renderer reads this; it does not reach back into the
analyzer.

```python
report.findings          # tuple[Finding, ...]
report.vulnerabilities   # FAIL only
report.score             # ScanScore, with per-category breakdown
report.coverage          # fraction that actually settled the question
report.rejected          # observations refused, with reasons
report.by_category()     # grouped
report.to_dict()         # JSON-serializable
```

`coverage` matters: a scan of ten plugins where six were inconclusive is a different statement from
one where all ten reached a verdict, and a report showing only "no failures" cannot distinguish them.

---

## Developer guide

Analyzing stored results:

```python
from ragstrike.analyzers.base.observation import Observation
from ragstrike.analyzers.config import build_engine
from ragstrike.database.repositories.finding_repository import FindingRepository

engine, _ = build_engine()
observations = [
    Observation.from_plugin_result(r, category=manifest_category(r.plugin_slug))
    for r in await ScanRepository(db).results_for(scan_id)
]
report = await engine.analyze_and_store(observations, FindingRepository(db), scan_id=scan_id)
```

Testing needs no database and no config tree — `AnalyzerEngine()` works with built-in defaults, and
every engine is pure:

```python
from ragstrike.analyzers.rules.rule_engine import RuleEngine, RuleSet, Rule, Condition

engine = RuleEngine(RuleSet(rules=(
    Rule(id="r1", conditions=(Condition("has_evidence", "eq", False),),
         status=PluginOutcome.INCONCLUSIVE),
)))
assert engine.evaluate(observation).overrode_plugin
```

**Keep analyzers pure.** No network, no database, no clock beyond the finding's timestamp. Purity is
what lets stored observations be re-analyzed offline after a rule change rather than re-scanned.

**Prefer a rule to a code change.** If a grading decision can be expressed as a condition, it belongs
in `rules.yaml` where an operator can see and change it.

---

## Extension guide

**Add a rule** — append to `rules.yaml`. No code.

**Add a scoring dimension** — add a method to `ScoreEngine`. Existing levels are untouched, which is
how "extensions without modifying existing analyzers" is met concretely.

**Add a confidence factor** — add a field to `ConfidenceConfig`, parse it in `from_mapping`, use it
in `compute`. It appears in `components` automatically, so the score stays decomposable.

**Add a specialised analyzer** — subclass `BaseAnalyzer`, declare `handles`, register it:

```python
from ragstrike.analyzers.registry import registry
from ragstrike.analyzers.engine import StandardAnalyzer

@registry.analyzer
class RetrievalAnalyzer(StandardAnalyzer):
    name = "retrieval"
    handles = ("context_poisoning",)
```

A specialist beats a generalist for its categories; a category with no specialist still gets analyzed
by the shipped one, which is what keeps a brand-new pack working on day one.

**Add a new evidence section** — add a field to `NormalizedEvidence` and populate it in
`EvidenceEngine.normalize`. Unrecognised keys already survive in `structured`, so nothing is lost
before you get to it.

**Store rules in a database** — `load_ruleset` is a free function returning a `RuleSet`. A
database-backed loader builds the same object; nothing else changes.

---

## Known limits, stated plainly

- **Category must be supplied by the caller.** `PluginResult` does not record it, so
  `Observation.from_plugin_result` takes it as an argument. A caller that omits it gets a finding
  whose category-scoped rules and advice never match — recorded as a validation warning, not an
  error.
- **No CLI command yet.** The engine is a library this phase; wiring `ragstrike analyze` belongs with
  the reporting work.
- **Re-analysis accumulates.** Running the analyzer twice over the same scan produces two sets of
  findings, distinguishable by `analyzer_version` and timestamp. That is deliberate — history is
  append-only — but there is no deduplication or "latest only" query yet.
- **The shipped rules grade four categories.** Anything else falls through to `unclassified-failure`
  at MEDIUM. Correct, but a new pack deserves its own rule.

---

## Where things live

| Concern | Path |
|---|---|
| Finding, Observation, ports | `src/ragstrike/analyzers/base/` |
| Rule engine | `src/ragstrike/analyzers/rules/` |
| Scoring | `src/ragstrike/analyzers/scoring/` |
| Confidence | `src/ragstrike/analyzers/confidence/` |
| Evidence normalization | `src/ragstrike/analyzers/evidence/` |
| Recommendations | `src/ragstrike/analyzers/recommendations/` |
| Registry | `src/ragstrike/analyzers/registry/` |
| Validation | `src/ragstrike/analyzers/validators/` |
| Orchestration | `src/ragstrike/analyzers/engine.py` |
| Config loading | `src/ragstrike/analyzers/config.py` |
| Persistence | `src/ragstrike/database/repositories/finding_repository.py` |
| Configuration | `configs/analyzer/` |
| Tests | `tests/unit/test_analyzer_*.py`, `tests/integration/test_analyzer_integration.py` |
