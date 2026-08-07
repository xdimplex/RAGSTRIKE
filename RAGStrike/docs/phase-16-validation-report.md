# Phase 16 — Production readiness, validation & quality assurance

> Every number here was measured on 2026-07-31 by running the command shown. Nothing is asserted from
> reading the code.

---

## 1. Issues found

Nineteen. Grouped by how they were found, because that turned out to be the most useful axis: **the
four most serious were invisible to the test suite and only appeared when the running system was
driven.**

### Found by reading configuration

| # | Issue | Severity |
|---|---|---|
| 1 | **`configs/ragstrike.yaml` was dead.** The SDD, `INSTALL.md`, and three package READMEs all named it as the configuration file. The loader read `configs/config.yaml`. Editing the documented file changed nothing and said nothing | **High** |
| 2 | **Its schema had drifted too** — `local_pack_dirs`, `disabled_packs`, `database_url`, `redact_secrets` are fields the model has never had | High |
| 3 | **Unknown configuration keys were silently ignored.** Pydantic defaults to `extra="ignore"`, so `max_concurency: 8` was accepted, discarded, and the default used — a scan running with settings nobody chose | **High** |
| 4 | **`configs/profiles/{quick,standard,deep}.yaml` were never read by anything.** The dashboard offered a profile picker backed by three hardcoded fallbacks; the CLI had no `--profile` flag; the SDK referenced "future profile-based scan selection" | **High** |
| 5 | **`engine.retry` was in the shipped config and absent from the schema**, so it was discarded on every load | Medium |
| 6 | `deep.yaml` writes `packs: ["*"]`. Read literally that is one pack named `*`, matching nothing — a deep scan running zero plugins, reporting no findings, indistinguishable from a clean result | **High** |

### Found by the type checker

| # | Issue | Severity |
|---|---|---|
| 7 | **`PluginManager.list()` shadowed the builtin inside its own class.** Every `-> list[...]` annotation in the class body resolved to the *method*, so `validate()`'s return type was unresolvable and the CLI's iteration over it was reported as iterating a non-iterable | **High** |
| 8 | `ScanEngine.__init__` took its two repositories **unannotated** — the composition root's most important wiring had no contract at all, because annotating them would have broken the layer contract | Medium |
| 9 | Four more missing annotations, one bare `dict`, one bare `tuple`, one wrong return type | Low |

### Found by reviewing capability against the claim

| # | Issue | Severity |
|---|---|---|
| 10 | **`src/ragstrike/api/` was five empty `__init__.py` files.** Not "handlers missing" — no routing, no schemas, nothing. The dashboard reported `BACKEND OFFLINE` because nothing existed behind the address | **Critical** |
| 11 | **The adapter could not talk to any API but VulnerableRAG's.** Hardcoded `POST`, a flat top-level prompt field, a dotted-path resolver that could not index a list, no authentication of any kind, no retry | **Critical** |
| 12 | **`jsonpath-ng` had been a declared dependency since Phase 1 and nothing imported it** — `requirements.txt` says it is for "configurable request/response mapping in the HTTP adapter" | Medium |
| 13 | **PDF had been a placeholder for fifteen phases behind a dependency that cannot install.** WeasyPrint binds to GTK/Pango/Cairo, absent from a stock Windows machine and unobtainable through `pip` | **High** |
| 14 | `jinja2` declared and unused — the design deliberately formats templates rather than evaluating them | Low |

### Found by driving the running system

**The four that matter most.** Every one passed the full test suite as it stood.

| # | Issue | Severity |
|---|---|---|
| 15 | **`POST /scans` returned an id that could not be queried.** The engine minted its own `ScanSession` id, so `GET /scans/{id}` 404'd on the id the client had just been handed. `/progress` masked it by falling back to an in-memory dict keyed on the other id | **Critical** |
| 16 | **A cancelled scan never reached a terminal state.** `asyncio.CancelledError` derives from `BaseException`, not `Exception`, so neither handler caught it and the row stayed in `PREPARING`/`RUNNING` **forever**. Two such rows were sitting in the development database from earlier sessions. A scan stuck in RUNNING reads, months later, as one that is still going | **Critical** |
| 17 | **Progress reported a numerator and no denominator.** `total` was assigned only after the engine returned, so a live scan reported `completed: 7, total: 0, percent: 0.0` — a progress bar frozen at zero for the entire run | **High** |
| 18 | **`status_for()` resolved by dict order, not specificity.** `TargetNotFoundError` *is* a `ConfigurationError`, so `GET /targets/unknown` answered **400** instead of 404 | Medium |

### Found by the architecture linter

| # | Issue | Severity |
|---|---|---|
| 19 | A `ragstrike serve` subcommand was written and `lint-imports` **correctly refused it**. `cli`, `api`, and `dashboard` are siblings on one layer row — three independent front doors, none of which may import another. The subcommand would have made an install without FastAPI unable to run a scan | Medium |

---

## 2. Root cause

Three patterns account for all nineteen.

**Design and implementation diverged and nothing checked.** Issues 1, 2, 4, 5, 12, 14 are all the
same shape: a file, a key, or a dependency that the design declared and the code never used. Nobody
was wrong at any single moment; the two drifted, and there was no mechanism that could notice. The
fix is not only to reconcile them but to make the reconciliation **enforced** — `extra="forbid"`
means a key with no field is now a startup error naming the field path.

**"Works against the lab" was mistaken for "works".** Issues 11 and 13 are capability gaps that
looked like completeness because the only target ever exercised was the one the defaults were written
from. The adapter's tests all passed; they all used `POST /chat`.

**Unit tests cannot see lifecycle bugs.** Issues 15, 16, and 17 are the important ones. Every one
survived 1,376 passing tests, because each needs a *running* system with a *real* async task to
manifest. They were found within ten minutes of starting a server and issuing four HTTP calls by
hand.

---

## 3. Files modified

**Created (23)**

```
src/ragstrike/api/app.py · deps.py · errors.py · service.py
src/ragstrike/api/routers/{system,targets,packs,scans,reports}.py
src/ragstrike/api/schemas/models.py
src/ragstrike/api/middleware/correlation.py
src/ragstrike/api/streaming/progress.py
src/ragstrike/core/config/profiles.py
src/ragstrike/core/contracts/repositories.py
src/ragstrike/target_adapters/fastapi/{auth,mapping}.py
tests/unit/{test_profiles,test_adapter_mapping,test_pdf_renderer}.py
tests/integration/test_api.py
docs/phase-16-validation-report.md
```

**Rewritten (2)** — `target_adapters/fastapi/adapter.py`, `reporters/pdf/renderer.py`

**Modified (21)** — the config loader and models, the scan engine, the scheduler, the CLI, the plugin
manager, both repositories, the plugin loader, the renderer base and report engine, the export
manager, `pyproject.toml`, `ruff.toml`, `configs/ragstrike.yaml`, and six test modules.

**Deleted (1)** — `configs/config.yaml`.

---

## 4. Exact changes

### Configuration

`configs/ragstrike.yaml` is now the file the loader reads. `resolve_config_file()` prefers it and
falls back to `config.yaml` with a `DeprecationWarning` naming the rename, so an existing checkout
keeps working; support ends at 2.0 per the deprecation policy. `extra="forbid"` on all six settings
models. `RetrySettings` added and wired into the adapter. `configs/config.yaml` deleted.

### Scan profiles

`core/config/profiles.py`: `ScanProfile` with `selects()`, wildcard expansion, path-traversal refusal
on the profile name, and strict field validation. Threaded through `load_settings(profile=...)`,
`ScanScheduler.plan(profile=...)`, `ScanEngine.run(profile=...)`, `ragstrike scan --profile`, a new
`ragstrike profiles` command, and `GET /api/v1/profiles`.

A profile may raise or lower **engine limits only**. It cannot touch safety, storage, or plugin
discovery — depth is the operator's choice, the safety envelope is not, and a "depth preset" that
could set `allow_remote_targets` would be a way to reach a third party by editing a file that does
not look like it does that. There is a test for it.

Anything a profile excludes becomes a **recorded skip with a reason**, never a silent omission, so a
quick scan can never be mistaken for a full one (ADR-020).

### Target adapter

Configurable HTTP method (`POST`/`PUT`/`PATCH`/`GET`, validated at construction). Nested request
mapping, so `prompt_field: "input.query"` produces `{"input": {"query": ...}}`. JSONPath response
mapping — a path starting with `$` is JSONPath, anything else is a dotted path; **the syntax decides,
not a flag**. Authentication (`bearer`/`api_key`/`basic`) whose credential comes **only** from an
environment variable, with no schema field a literal secret fits in, and a `__repr__` that never
renders the value. Retry with exponential backoff and jitter on transport failures, 429, and 5xx.

**Never on a refusal, and never on any other 4xx.** A target declining to answer is the most
interesting result an attack pack can get; retrying it would resend the payload, inflate the attempts
count, and corrupt the `successes / attempts` ratio the scoring model rests on. There is a test named
after exactly that.

The extensibility claim is now under load: **four APIs — `POST /chat`, `POST /generate`,
`PUT /query`, `POST /ask` — sharing no path, method, request shape, or response shape, all driven
through one adapter with nothing but `options`.**

### The API

Seventeen paths under `/api/v1`, matching the contract the dashboard was already written against, so
**no dashboard code changed**. One error envelope for every failure including validation errors.
Correlation ids, sanitised against log injection. SSE progress streaming that always terminates.
Background scans with cancellation. OpenAPI at `/api/v1/docs`.

Loopback-only with no `--host` flag, and no authentication — **stated plainly** in the module
docstring and the OpenAPI description rather than left to be discovered. Targets are read-only over
HTTP: a target carries an authorization record naming who approved testing it, and one created by an
unauthenticated local call would be self-issued.

Shipped as a separate `ragstrike-api` console script rather than a `ragstrike serve` subcommand,
because the layer contract refused the subcommand and it was right to.

### PDF

ReportLab, pure Python, installs everywhere. `implemented` is **computed from whether the import
succeeded**, not hardcoded — so the format degrades honestly when the extra is absent, with an install
hint. `BaseRenderer` gained `binary` and `render_bytes()`; the exporter writes bytes for binary
formats, because round-tripping a PDF through UTF-8 produces a file with the right name that no
reader can open.

All text is escaped before it reaches ReportLab's mini-markup. A report carries model output and
retrieved document text — both attacker-influenced by construction, since getting text into the
corpus *is* the attack.

### Lifecycle fixes

`ScanEngine.run()` accepts `scan_id` so the API can hand out an id the engine then uses, and calls
`on_plan(total)` as soon as planning finishes. A new `_terminate()` is on **every** exit path
including an explicit `except asyncio.CancelledError` that persists `CANCELLED` under
`asyncio.shield` — unshielded, the write would itself be cancelled and never land.

---

## 5. Why each change was required

Every fix above traces to one of three failures the project already had a stated position on:

**A control that isn't enforced isn't a control.** "Never put a secret in this file" was a comment
above a schema that had a field a secret fit in. Now it does not. "Configuration is validated" was
true of values and false of keys. Now it is true of both.

**Silence is the worst failure mode this tool has.** A dead config file, an ignored key, a wildcard
matching nothing, a progress bar at 0%, a scan row stuck in RUNNING, a `--plugins` flag that does not
exist — each produced a plausible-looking result with no error. That is the same class of failure as
reporting `INCONCLUSIVE` as `PASS`, which this project has refused since Phase 6.

**A claim on the box has to be testable.** "Any third-party RAG without touching plugin code" was
never exercised against a second API shape. It is now, four times, and the test says in its docstring
that a change to `adapter.py` to make it pass means the README needs rewriting first.

---

## 6. Remaining risks

**No full differential scan has been completed.** Unchanged from v1.0.0 and still the single largest
gap. The framework's central claim — that it separates a vulnerable RAG from a hardened one — is
built, instrumented, and now genuinely exercisable end to end over HTTP, but the multi-hour run
against the live lab pair has not been done. [`validation-results.md`](validation-results.md) and
[D-04](technical-debt.md).

**The API has no authentication.** The only control is that the socket is unreachable from outside
the machine. Documented in three places. If that ever stops being true, authentication has to arrive
in the same change.

**Plugins are still not sandboxed.** Installing a pack grants it the trust of installing a Python
package. Roadmap R-07.

**`reports.py` sits at 38% coverage.** The generation and download paths need a scan with findings in
the database; the tests cover the guard clauses and the traversal refusal, not the happy path. Honest
gap, not a hidden one.

**Nine of twelve catalogued attack packs remain unimplemented.** Listed in
[`plugin-index.md`](plugin-index.md).

**Two scan rows in the development database are stuck in `RUNNING`** from before fix #16. Historical
data, not a live defect; the code path that created them is closed.

---

## 7. Architecture validation

| Question | Answer |
|---|---|
| Layer contracts | **6 of 6 kept**, across 311 files and 1,184 dependencies |
| Import-time circular imports | **0** |
| Deferred cycles | 1, deliberate and documented at the site |
| Dead modules | **0** |
| Did the architecture hold under the new code? | **Yes, and it did real work** |

The contract caught a `cli → api` import the moment it was written, and refusing it was correct. The
`ScanEngine` repositories could not be typed against the concrete classes without breaking the
dependency rule — the answer was Protocol ports in `core/contracts/`, not an exception to the rule.
The scheduler takes a narrow `ProfileSelector` protocol rather than importing `ScanProfile` from
`core.config`, which it may not do.

**Three separate times the architecture said no and was right.** That is the strongest evidence in
this report that the layering is load-bearing rather than decorative.

---

## 8. Production readiness

| Dimension | Score | Note |
|---|---|---|
| Build & install | 10/10 | Clean, no native dependencies, `pip install -e ".[dev]"` |
| Tests | 9/10 | 1,419 passing, 89.8% coverage; reports router thin |
| Static quality | 10/10 | mypy strict **clean for the first time**, ruff clean, black clean |
| Architecture | 10/10 | 6/6 contracts, 0 cycles, 0 dead modules |
| Configuration | 9/10 | Single source, strict keys, profiles live |
| API | 9/10 | 17 paths, one envelope, OpenAPI; no auth by design |
| Dashboard | 9/10 | Verified live against the real API through its own transport |
| Reporting | 10/10 | Four formats, all writing real files |
| Extensibility | 10/10 | Four API shapes by configuration; zero-edit packs enforced |
| Error handling | 9/10 | Every exit path terminal; hints survive the HTTP boundary |
| **Validation** | **4/10** | **The differential run is still not done** |

**Overall: 8.5 / 10.** The framework is production-ready. Its central claim is still undemonstrated.

## 9. Security readiness

| Dimension | Score | Note |
|---|---|---|
| Secrets handling | 10/10 | No schema field a literal secret fits in; env-only; `repr` masked |
| Target scoping | 10/10 | Loopback-only default at one chokepoint; profiles cannot widen it |
| Authorization | 10/10 | Persisted record; not creatable over HTTP |
| Injection surfaces | 10/10 | No `eval`/`exec`/`subprocess`/`shell=True`/`pickle` anywhere |
| Path traversal | 10/10 | Report downloads, profile names, and filenames all constrained and tested |
| Log hygiene | 10/10 | No document, question, or answer text; correlation ids sanitised |
| Output escaping | 10/10 | HTML and PDF both escape attacker-influenced text |
| Static analysis | 10/10 | bandit: 0 issues |
| Rate limiting | 9/10 | No disable path; retry never amplifies a refusal |
| **API authentication** | **5/10** | **None. Loopback is the only control** |
| Plugin sandboxing | 4/10 | None. Trust model documents it |

**Overall: 9.0 / 10.** Both deductions are documented, deliberate, and roadmapped.

---

## 10. Go / No-Go

### **GO**, with one condition stated plainly.

**Ship it as a framework.** It builds, installs, runs, and the pieces that were declared-but-absent —
the API, PDF, profiles, third-party adapter support — are now built and tested. mypy is clean for the
first time in the project's history. Nineteen defects were found and all nineteen are fixed.

**Do not yet claim it finds real vulnerabilities.** No full differential run has been completed. That
is the same caveat v1.0.0 shipped with, and Phase 16 did not change it, because it needs hours of
wall clock rather than code.

The single highest-value thing that can be done next needs no engineering at all: **start both lab
applications and run the differential.** Everything required to do it now exists and is verified —
including, for the first time, the ability to watch it happen over HTTP.

### The finding worth carrying forward

Three critical defects — an unqueryable scan id, a scan that could never leave `RUNNING`, and a
progress bar frozen at zero — **passed 1,376 tests and were found in ten minutes of running the
server by hand.**

A test suite proves the pieces behave. It does not prove the system works. Both are needed, and this
project had been buying only the first.

---

## Reproduce

```bash
pytest -q                                   # 1,419 passed
pytest --cov=src/ragstrike -q               # 89.8%
mypy src                                    # clean
ruff check . && black --check .             # clean
lint-imports                                # 6 kept, 0 broken
bandit -c pyproject.toml -r src/ragstrike   # 0 issues
python -m validation.runner --checks-only   # 10/10
python -c "from validation.runner.audit import collect; print(collect().to_dict())"
ragstrike-api                               # then open http://127.0.0.1:8000/api/v1/docs
```
