# Validation results

> What was actually run against this build, and what it showed — including what it did not establish.
>
> Regenerate with `python -m validation.runner`. The machine-readable form is
> `validation/reports/validation-summary.json`.

---

## Environment

| Item | Value |
|---|---|
| RAGStrike | 0.3.0 (plugin API 1.0.0) |
| Python | 3.11.15 |
| Platform | Windows 10, CPU-only |
| Model | Qwen3 4B via Ollama; `nomic-embed-text` for embeddings |
| Targets | VulnerableRAG on 9000, SecureRAG on 9001 |
| Corpus | The same three benign PDFs in both, 4 chunks each |

The corpus being identical is not a detail. A differential over different corpora measures the
corpora.

---

## 1. Test suites

| Suite | Tests | Result |
|---|---|---|
| RAGStrike | 1,326 | pass |
| SecureRAG | 248 | pass |
| Validation harness | 26 | pass |

Six import-linter contracts kept, including *Dashboard never imports the engine* and *Scoring cannot
reach a model or any I/O*.

---

## 2. Consistency checks

All ten pass.

| Check | Detail |
|---|---|
| Configuration loading | 2 targets; `allow_remote=False`; 3 plugin directories |
| Plugin discovery | 9 active, 0 refused |
| Attack SDK | plugin API 1.0.0; 38 exports |
| Analyzer output | 1 analyzer registered; no config missing |
| Finding generation | constructs and scores |
| Report generation | 3 formats — html 7,953 B, json 4,557 B, markdown 2,218 B |
| Database integrity | 4 migrations applied, versions `[1, 2, 3, 4]`, no gaps |
| Logging | level INFO, JSON lines, directory present |
| Dashboard integration | 9 pages resolve, none unresolved |
| Target communication | both targets reachable through the real adapter and scope policy |

---

## 3. Performance

Single samples from one machine. No warm-up, no repetition. Useful for order of magnitude and for
catching a regression that changes one; **not** for fine-grained comparison.

| Measurement | Value |
|---|---|
| Startup (cold import, fresh process) | 1,124 ms |
| Plugin discovery (9 plugins, first import) | 109 ms |
| Analyzer / report model (50 findings) | 0.9 ms |
| Report generation (3 formats, 109 KB) | 3.5 ms |
| Dashboard wiring (9 page modules) | 0.1 ms |
| Peak memory | 54 MB |
| Database size | 0.09 MB |

**The framework is not the slow part.** Everything it does itself is milliseconds; scan duration is
target model inference, and on CPU that is the entire wall-clock cost.

---

## 4. The differential run

### What was run

The runner scanned both halves of the lab through the real `ScanEngine`, evaluated all 15 benchmarks
against those scans, and produced a comparison. The loop is proven end to end:

```
dataset -> ScanEngine -> plugin results -> benchmark evaluation -> comparison -> report
```

| Metric | Value |
|---|---|
| Benchmarks evaluated | 30 (15 benchmarks x 2 targets) |
| Validated | 2 |
| Mismatched | **0** |
| Did not run | 28 |
| Pass rate (of those that ran) | 100% |
| Separating the two targets | **0 of 15** |

### Why 28 did not run, and why that is stated rather than hidden

**The plugin set was deliberately reduced to the reference pack for this run.** Everything else was
disabled, so every benchmark naming a real attack pack reports `NOT_RUN` with the reason
(`plugin(s) not installed or not scheduled: ...`) rather than a fabricated result.

The reason is measured, not assumed:

| Observation | Value |
|---|---|
| Scan duration, 1 plugin / 3 payloads, cold model | **122 s** per target |
| Same scan, warm model | 16 s and 32 s |
| Implied cost per payload | ~5–40 s on this CPU |
| A `standard` profile is ~340 cases | **hours per target** |

An earlier attempt at the full run reached 46 payloads against VulnerableRAG in roughly an hour
before it was stopped. On GPU-backed inference this is an unremarkable overnight job; on this
machine it is not something that completes inside a working session.

**So the honest position is:** the harness, the engine, the analyzer, the reporting path, and the
comparison logic are all proven against the live pair. **The differential itself — VulnerableRAG
grading badly and SecureRAG grading cleanly — is not yet demonstrated end to end**, and this document
says so rather than implying otherwise.

### What the one benchmark that ran shows

`GR-01` (the plugin lifecycle executes end to end) validated on **both** targets, as its dataset
expects. That is not a trivial result:

- Discovery, scheduling, execution, result collection, analysis, and reporting all work against two
  independently running applications.
- **SecureRAG's seven-control chain does not break the lifecycle.** A control that refused everything
  would have failed here, which is precisely what `general_rag_behaviour.yaml` exists to catch.

`Separates: 0 of 15` is correct and expected for this run: the only benchmark that executed is one
whose dataset expects the *same* outcome from both halves. It is reported prominently anyway, because
a run in which nothing separated the two targets has established nothing about the difference between
them — and that sentence should be uncomfortable to read, not buried.

### A defect this run found

The first version reported a comparison whose two halves both `NOT_RUN` as **`MISMATCH`** — turning
"you disabled some plugins" into "the scanner is broken". The summary totals were right; the
comparison table was not. Fixed in `Comparison.status`, with a regression test named after the
failure.

### To complete the differential

```bash
# both applications running, same corpus in both, every plugin enabled
python -m validation.runner --targets vulnerable-rag secure-rag
```

Budget hours per target on CPU, or use GPU-backed inference. The command is unchanged; only the
plugin set and the patience differ.

---

## What this validation does not establish

- **Behaviour against any RAG application other than these two.** The lab is a controlled pair, and
  a scanner that works on it has been shown to work on it.
- **Behaviour under concurrent scans**, with a different model, or over a large corpus.
- **That a clean SecureRAG result means SecureRAG is secure.** It means the shipped packs did not
  find what they test for. Eight of twelve catalogued packs are not built.
- **Anything about the eight unbuilt packs**, the unimplemented API server, or PDF rendering. See
  [`limitations.md`](limitations.md).
