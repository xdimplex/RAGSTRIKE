# RAGStrike validation report

> Generated 2026-07-31T03:02:50.484749+00:00

## Environment

| Item | Value |
|---|---|
| RAGStrike version | 1.0.0 |
| Plugin API version | 1.0.0 |
| Python | 3.11.15 |
| Platform | Windows 10 |
| Targets | vulnerable-rag, secure-rag |

## What did not pass

Nothing. Every consistency check passed and every benchmark matched.

## Totals

| Metric | Value |
|---|---|
| Benchmarks | 0 |
| Validated | 0 |
| Mismatched | 0 |
| Did not run | 0 |
| Pass rate (of those that ran) | 0.0% |
| Comparisons | 0 |
| Separating the two targets | 0 |

## Consistency checks

| Check | Status | Detail | ms |
|---|---|---|---|
| Configuration loading | PASS | 2 target(s); safety allow_remote=False; 3 plugin dir(s) | 6 |
| Plugin discovery | PASS | 9 active, 0 refused | 149 |
| Attack SDK | PASS | plugin API 1.0.0; 38 export(s) | 0 |
| Analyzer output | PASS | 1 analyzer(s) registered; config missing=none | 43 |
| Finding generation | PASS | Finding constructs; risk=7.0 | 0 |
| Report generation | PASS | 4 format(s): html=7953B, json=4557B, markdown=2218B, pdf=91B | 217 |
| Database integrity | PASS | 4 migration(s) applied: [1, 2, 3, 4] | 46 |
| Logging | PASS | level=INFO; json_lines=True; dir=D:\Project\RAGStrike\logs | 3 |
| Dashboard integration | PASS | 9 page(s) resolve; unresolved=none | 64 |
| Target communication | PASS | skipped: no targets requested | 5 |

## Performance

> Single-sample measurements from one machine. Useful for order of magnitude and for catching a regression that changes one; not for fine-grained comparison.

| Measurement | Value | Unit | Note |
|---|---|---|---|
| Startup time | 1251.31 | ms | cold import, fresh process |
| Plugin discovery time | 114.738 | ms | 9 plugin(s), first import |
| Analyzer/report-model duration | 0.886 | ms | 50 findings, deterministic arithmetic |
| Report generation time | 4.244 | ms | 4 format(s), 109,402B total |
| Dashboard wiring time | 0.102 | ms | 9 page module(s) imported |
| Peak memory | 61.516 | MB | GetProcessMemoryInfo |
| CPU time | 1.672 | s | user+system for the validation process |
| Database size | 0.141 | MB | D:\Project\RAGStrike\data\scans.db |
| Scan duration | 0.0 | ms | no scan in this run |
