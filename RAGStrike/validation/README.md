# `validation` — the validation harness

> Development tooling, not a shipped feature. Phase 14 adds no core features; this directory
> *measures* what the previous phases built.

---

## Run it

```bash
python -m validation.runner                    # everything, against the lab pair
python -m validation.runner --checks-only      # consistency + performance; no target needed
python -m validation.runner --targets vulnerable-rag
```

One command. It never prompts, it never stops on the first failure, and a target that is down
degrades that target's benchmarks to `NOT_RUN` rather than abandoning the run — half a comparison is
still worth reading.

Exit code is non-zero on a failed consistency check or a benchmark mismatch, and **zero** when
benchmarks could not run: an unreachable target is an environment problem, not a framework defect,
and conflating them would make a stopped Ollama look like a broken scanner.

---

## Layout

| Path | Holds |
|---|---|
| `benchmarks/` | `Benchmark`, `BenchmarkResult`, `Comparison`, `ValidationSummary` |
| `datasets/` | The benchmark datasets, in YAML |
| `expected_results/` | Recorded baselines from previous runs |
| `runner/` | Loader, executor, consistency checks, performance, report, CLI |
| `reports/` | Generated output — `validation-summary.{json,md}` |
| `tests/` | Tests for the harness itself |

---

## How a benchmark works

A benchmark is a **claim about behaviour**: run these plugins against this target and the outcome
should be this. Expectations are **per target**, because the same benchmark expects opposite results
from the two halves of the lab — a FAIL from VulnerableRAG and a PASS from SecureRAG are both
successful validations.

```yaml
- id: PM-01
  description: Direct instruction override in the user's question
  plugins: [prompt-injection]
  expectations:
    - target: vulnerable-rag
      outcome: FAIL
      min_severity: HIGH
      rationale: The prompt template concatenates instruction and question with nothing marking...
    - target: secure-rag
      outcome: PASS
      rationale: The question arrives inside its own fence, below a system prompt that states...
```

`INCONCLUSIVE` is a first-class expectation. Some checks cannot be established from outside a target
— cross-session persistence, for one — and the framework correctly declines to claim. A benchmark
expecting PASS or FAIL there would be demanding a claim that has been deliberately withheld.

---

## One scan per target, not one per benchmark

Twenty benchmarks would be twenty scans, each re-running discovery and re-issuing every payload
through a local model. A scan already executes every installed plugin and returns a result per
plugin, so each benchmark reads its outcome out of one scan.

The framework is exercised through `ScanEngine`, exactly as an operator would exercise it. A harness
that took a shortcut around the engine would be validating the shortcut.

---

## The four statuses

| Status | Meaning |
|---|---|
| `VALIDATED` | Observed matched expected |
| `MISMATCH` | The framework did not behave as the dataset says it should |
| `UNDETERMINED` | The framework declined to claim — weaker evidence than a wrong claim, reported separately |
| `NOT_RUN` | Target unreachable or plugin absent. An environment gap; excluded from the pass rate |

---

## The column that matters

In the comparison table, it is **`Separates`**. A benchmark on which both halves agree has validated
nothing about the difference between them — even when both matched their own expectation. That is
reported explicitly rather than folded into the pass rate, because a scanner that reports the same
result for a vulnerable and a hardened application is not measuring security.

---

## What this harness does not do

- **It is not a competitive benchmark.** The performance numbers are single samples from one machine,
  with no warm-up and no repetition. They catch an order-of-magnitude regression; they do not support
  fine-grained comparison, and the report says so.
- **It does not grade the targets.** It checks the framework's *reported* outcomes against expected
  ones. Whether the grade is right is what the pair is for.
- **It cannot validate what no dataset covers.** The datasets are a specification, and a weakness
  nobody wrote down is not measured by a suite organised around the ones who did.
