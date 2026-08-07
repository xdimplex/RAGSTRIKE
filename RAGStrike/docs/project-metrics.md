# Project metrics

> **Measured on 2026-07-30**, not estimated. Every number below has a command beside it or in the
> reproduction section at the bottom.

---

## Version

| | |
|---|---|
| Framework version | **1.0.0** |
| Plugin API version | **1.0** (moves independently — ADR-015) |
| Scoring model version | 1 |
| Python | 3.11+ |
| Licence | Apache-2.0 |

## Code

| | |
|---|---|
| Source modules | **251** |
| Code lines (excluding blanks and comments) | **19,805** |
| Packages | **110** |
| Import-time circular imports | **0** |
| Dead (unreferenced) modules | **0** |
| Module docstring coverage | **76.1%** (191/251) |
| Package README coverage | **73.6%** (81/110) |

Plus the lab: **VulnerableRAG** and **SecureRAG**, ~190 files each.

## Tests

| | |
|---|---|
| Tests | **1,327 passing**, 0 failing, 0 skipped |
| Line + branch coverage of `src/ragstrike` | **89.9%** |
| Statements covered | 5,534 of 6,044 |
| Runtime | ~172 s |
| Architectural contracts enforced | **6 of 6** |
| Framework consistency checks | 10 |
| Validation benchmarks | 15, across 4 datasets |

The uncovered 10% is concentrated in `target_adapters/fastapi/adapter.py` (39%) — the code that talks
to a live target over HTTP. **Covering it properly needs a running target, not a mock**, and a mocked
HTTP adapter would test the mock. Honest gap rather than a padded number.

## Plugins

| Kind | Count | Slugs |
|---|---|---|
| Attack packs | **3** | `prompt-injection` · `prompt-leakage` · `context-poisoning` |
| Evaluation packs | **5** | `prompt-boundary` · `context-separation` · `instruction-priority` · `source-attribution` · `retrieval-consistency` |
| Diagnostic | **1** | `dummy-attack` |
| **Discovered total** | **9** | `ragstrike plugins` |
| **Declared, not implemented** | **9** | Annex B catalog — directories exist, code does not |

Twelve packs are specified in [Annex B](annex-b-attack-catalog.md); three are built. The gap is listed
in [`plugin-index.md`](plugin-index.md) rather than left to be discovered.

## Evaluation categories

| Category | Covered by |
|---|---|
| Prompt-structure integrity | 3 packs |
| Answer provenance | 1 pack |
| Retrieval stability | 1 pack |
| Citation grounding | **not implemented** |
| Answer faithfulness | **not implemented** |
| Retrieval integrity | **not implemented** |

Three of six. [`evaluation-pack-index.md`](evaluation-pack-index.md).

## Adapters

| Adapter | State |
|---|---|
| `fastapi` | **Implemented** — the lab pair and any HTTP RAG API |
| `openai` · `ollama` · `langchain` · `llamaindex` · `local` | **Declared in `PLANNED`, not implemented** |

One working adapter. It is registered in the same registry the planned ones occupy, so each of those
is a class plus a registration — but none of them exists today.

## Report formats

```python
{'html': True, 'json': True, 'markdown': True, 'pdf': False}
```

Three render; **PDF is declared and refuses** rather than writing a file that would not open
([D-05](technical-debt.md)). Real output: [`../examples/example_reports/`](../examples/example_reports/).

## Quality gate

| Tool | Result |
|---|---|
| `pytest` | 1,327 passed |
| `lint-imports` | 6/6 contracts kept |
| `ruff check .` | All checks passed |
| `black --check .` | 323 files unchanged |
| `bandit -r src/ragstrike` | 0 issues (6 false positives justified at the site) |
| `mypy src` | **11 errors** in pre-Phase-10 code — [D-01](technical-debt.md), ADR-024 |

## Documentation

| | |
|---|---|
| Documents under `docs/` | 45 |
| Architecture Decision Records | **24** |
| Package READMEs | 81 |
| Website source pages | 7 |
| Worked examples | 8 directories |

## Delivery

| | |
|---|---|
| Phases completed | **15** |
| Repositories | 3 (RAGStrike, VulnerableRAG, SecureRAG) |
| Database migrations | append-only, never edited in place |

---

## What the numbers do not say

**No real attack findings exist.** The database holds diagnostic runs only. The full differential
against the live lab pair is a multi-hour job that has not been completed —
[`validation-results.md`](validation-results.md), [D-04](technical-debt.md).

1,327 tests and 89.9% coverage measure whether the framework behaves as designed. **They do not
measure whether it finds real vulnerabilities**, and no number on this page does. That question is
answered by running the differential, and it is still open.

---

## Reproduce

```bash
python -c "from validation.runner.audit import collect; print(collect().to_dict())"
pytest --cov=src/ragstrike -q
ragstrike plugins
lint-imports && ruff check . && black --check . && mypy src
bandit -c pyproject.toml -r src/ragstrike
python -m validation.runner --checks-only
```
