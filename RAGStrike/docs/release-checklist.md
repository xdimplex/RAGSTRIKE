# Release checklist

> Run in order. Every item is either a command with a pass condition or a document to read.

---

## 1. The gate

```bash
pytest                          # expect: all pass
lint-imports                    # expect: 6 kept, 0 broken
mypy src                        # see the note below
ruff check .                    # expect: All checks passed
black --check .                 # expect: unchanged
```

**`mypy src` is not clean.** Eleven pre-existing errors in `plugins/`, `core/`, `cli/`, and
`database/` — untyped function parameters and two unreachable branches. They predate the phases that
introduced the current subsystems and are recorded here rather than suppressed. `mypy` on any
individual subsystem added in Phases 10–12 is clean.

## 2. Framework consistency

```bash
python -m validation.runner --checks-only
```

Expect: 10/10 checks pass.

## 3. Differential validation

```bash
# with VulnerableRAG on 9000 and SecureRAG on 9001, seeded with the same corpus
python -m validation.runner --targets vulnerable-rag secure-rag
```

Read `validation/reports/validation-summary.md`. The **`Separates`** column is the one that matters.

## 4. Compatibility of the lab pair

```bash
cd SecureRAG && pytest tests/parity
```

Expect: all pass. This is the drift gate.

## 5. Clean-environment install

See [`installation-validation.md`](installation-validation.md).

## 6. Versions agree

| Location | Value |
|---|---|
| `VERSION` | **1.0.0** |
| `src/ragstrike/__init__.py` `__version__` | **1.0.0** |
| `CITATION.cff` `version` | **1.0.0** |
| `pyproject.toml` `version` | **1.0.0** |

All four agree. `PLUGIN_API_VERSION` stays at **1.0** — the plugin contract did not change, and
bumping it every release teaches pack authors to ignore it ([`versioning-policy.md`](versioning-policy.md)).

## 7. Documents

- [ ] `CHANGELOG.md` has an entry for this release
- [ ] `RELEASE_NOTES.md` is current
- [ ] `docs/limitations.md` matches what is actually unbuilt
- [ ] `README.md` status banner names the current phase
- [ ] `SECURITY.md` disclosure contact is reachable

## 8. Licensing

```bash
pip-licenses --format=markdown            # if installed
```

See [`license-review.md`](license-review.md), which supersedes
[`third-party-attribution.md`](third-party-attribution.md) on dependency licensing. Confirm no new
dependency carries a copyleft licence incompatible with Apache-2.0 redistribution.

**Note:** the v1.0.0 review found four MPL-2.0 distributions and one tri-licensed
(GPLv2+/LGPLv2+/MPL-1.1) transitive dependency in the optional `pdf` extra. Neither creates an
obligation here — nothing is vendored — but the earlier claim that *no* copyleft dependency was
present was too strong, and is corrected on that page.

## 9. Repository hygiene

- [ ] `git status` clean
- [ ] No secret in any committed file — the lab canaries are synthetic and clearly labelled
- [ ] `data/`, `logs/`, `reports/`, `uploads/`, `.venv/` are gitignored
- [ ] Issue templates, PR template, and `CODEOWNERS` present under `.github/`

## 10. Quality checklist

Measured against this build.

| Item | Result |
|---|---|
| **No broken imports** | 249 modules imported, **0 failures** |
| **No dead code** | `ruff` F401/F841 clean across `src`, `tests`, `validation` |
| **Consistent folder structure** | 251 source modules; every package has a README stating its responsibility and what it must never contain |
| **Consistent naming** | `pep8-naming` (N) enforced; `ban-relative-imports = all` |
| **Configuration validation** | Fails fast at startup with the exact field path. Verified by the `Configuration loading` consistency check |
| **Documentation completeness** | 30 documents under `docs/`, plus a README per package |
| **Test coverage** | 1,326 RAGStrike + 248 SecureRAG + 26 harness = **1,600 tests**. Core coverage gate is 85%; `scoring` and `scheduler` are held higher because a bug there is invisible in output |
| **Benchmark execution** | See [`validation-results.md`](validation-results.md) |

### Two notes on what "clean" means here

**"No dead code" is a lint result, not a proof.** `ruff` finds unused imports and unused locals. It
does not find a function nobody calls, and this repository deliberately contains code that is *not
yet called* — the declared-but-unimplemented controls, the PDF renderer placeholder. Those are
documented as unbuilt rather than deleted, because a declared gap is more useful than a silent one.

**Coverage is not a quality measure on its own.** The number that matters here is not the percentage
but which tests exist: an import-linter contract that fails CI when the dashboard imports the engine
is worth more than a hundred lines of covered getters.

---

## 11. The honest read

Before tagging, re-read [`limitations.md`](limitations.md) and confirm every item still true is still
listed. **A release that quietly drops a limitation is worse than one that never claimed it.**


---

# v1.0.0 sign-off

Run on **2026-07-30**. Recorded as it came out, including the parts that did not pass.

| Criterion | State | Evidence |
|---|---|---|
| All tests passing | ✅ | 1,327 passed, 0 failed, 89.9% coverage |
| Import contracts | ✅ | 6 of 6 kept |
| Formatting and linting | ✅ | `black` 323 files unchanged · `ruff` all checks passed |
| Security linting | ✅ | `bandit` 0 issues; 6 false positives justified at the site |
| Static typing | ⚠️ | **11 pre-existing errors** — [D-01](technical-debt.md), [ADR-024](annex-c-adrs.md) |
| Structural audit | ✅ | 0 import-time cycles, 0 dead modules, 251 modules |
| Framework consistency | ✅ | 10 of 10 checks |
| **Differential validation** | ❌ | **Not completed** — [D-04](technical-debt.md), [`validation-results.md`](validation-results.md) |
| Lab parity | ✅ | `/openapi.json` compared; surfaces identical |
| Version numbers | ✅ | All four markers at 1.0.0 |
| Documentation | ✅ | 45 documents, 24 ADRs, 4 indexes, 8 examples |
| Licensing | ✅ | Reviewed; NOTICE present |
| Release artifacts | ✅ | Examples, real generated reports, website source, presentation set |

## The two that are not green

**`mypy src` — 11 errors.** In Phase 3–5 code. Fixing them means editing completed phases, which the
delivery discipline forbids; suppressing them means a green board made green by suppression, which
teaches maintainers that the board means nothing. Recorded with an estimate instead.

**The differential run has not been completed.** This is the honest blocker on the framework's central
claim. It needs no code — hours of wall clock with both lab applications running and identically
seeded.

## Tagging with those open

**Both are known, recorded, estimated, and stated in the README, the audit report, the metrics page,
and the limitations page.** Neither is discovered by a user; both are the first thing a reader is
told.

A 1.0.0 that overstates its evidence would be a worse release than one that ships with two documented
gaps. That is the judgement being made here, and ADR-024 records it as a decision rather than an
oversight.

## Before the tag

```bash
git status                      # clean
git tag -a v1.0.0 -m "RAGStrike v1.0.0"
```

Annotated, on the commit whose `VERSION` file matches — never before it.
