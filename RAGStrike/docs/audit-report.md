# Project audit & code-quality summary

> Measured, not asserted. Regenerate the structural half with:
>
> ```bash
> python -c "from validation.runner.audit import collect; print(collect().to_dict())"
> ```

---

## 1. Structure

| Measure | Value |
|---|---|
| Source modules | 251 |
| Code lines (excluding blanks and comments) | 19,805 |
| Packages | 110 |
| **Import-time circular imports** | **0** |
| **Unreferenced (dead) modules** | **0** |
| Module docstring coverage | 76% (191/251) |
| Package README coverage | 74% (81/110) |

### The one cycle, and why it is not a defect

The graph contains exactly one loop:

```
plugins.base.attack  ->  plugins.base.payloads  ->  plugins.base.attack
```

It **cannot deadlock**, and the source says so at the site:

- `attack.py` imports `payloads` under `if TYPE_CHECKING:` — never executed
- `attack.py` also imports it inside `load_payloads()` — a function body, executed at *call* time, when both modules are fully loaded
- `payloads.py` imports `Payload` from `attack` at module level — one direction only

Both halves are the standard resolution for a cycle, applied deliberately, with a comment explaining
why. The audit reports it under `deferred_cycles` rather than as a finding.

**Getting that classification right took three attempts, and the wrong ones are the interesting
part.** The first detector treated a package and its `__init__` as separate nodes and fanned every
package import out to all submodules — it reported **32 cycles**, nearly all of them ordinary
re-exports. The second fixed resolution and reported **1**, still wrong, because it did not model
deferred execution. Only the third asks what Python actually runs.

An audit that cries wolf gets ignored, and an ignored audit misses the real finding when one arrives.

### Naming and layout

- Absolute imports only — `ban-relative-imports = all`. Not style: `ragstrike.logging` shadows the
  stdlib `logging` inside this distribution, and absolute imports are what keep that unambiguous.
- `pep8-naming` (ruff `N`) enforced across the tree.
- Every package that has a README states its responsibility **and what it must never contain**. The
  "never" section is the load-bearing half.

### The documentation gap

29 packages have no README — mostly leaf subpackages under `analyzers/` and `dashboard/`
(`analyzers/scoring`, `dashboard/navigation`, and similar). Their parent packages are documented and
every module in them carries a docstring, so nothing is undocumented; the gap is one of navigation
rather than of explanation. Recorded in the [technical debt register](technical-debt.md).

---

## 2. Code quality

| Tool | Scope | Result |
|---|---|---|
| **black** | 323 files | clean |
| **ruff** | `src`, `tests`, `validation`, `plugins` | **All checks passed** |
| **bandit** | `src/ragstrike` | **0 issues** |
| **lint-imports** | whole package | **6 of 6 contracts kept** |
| **pytest** | `tests`, `validation/tests` | **1,327 passed** |
| **mypy** | `src` | **11 errors in 6 files** — see below |

### mypy is not clean, and that is recorded rather than suppressed

```
2  cli/output/console.py            missing parameter annotations
2  cli/main.py                      missing parameter annotations
1  cli/main.py                      statement unreachable
1  cli/main.py                      (related)
1  core/orchestrator/scan_engine.py missing parameter annotation
1  plugins/loader/loader.py         incompatible assignment
1  plugins/loader/loader.py         missing type arguments
1  plugins/registry/plugin_manager.py  missing parameter annotation
1  database/repositories/plugin_repository.py  missing type arguments
```

All eleven predate the subsystems added in Phases 10–14; `mypy` run against `analyzers/`,
`reporters/`, `dashboard/`, or `validation/` individually is clean. They are untyped parameters and
two unreachable branches — none is a correctness bug, and none is suppressed with a blanket ignore.

**Why they are not fixed here:** Phase 15 forbids modifying previous phases, and adding annotations
to `scan_engine.run()` or `cli.main.scan()` means touching Phase 3 and Phase 4 code. They are the
first entry in the [technical debt register](technical-debt.md) with an estimate.

### The six bandit findings, and why all six were false

| ID | Site | Verdict |
|---|---|---|
| B104 bind-all-interfaces | `dashboard/services/target_service.py` | `"0.0.0.0"` is a string being *matched*, not bound. That module opens no socket |
| B105 hardcoded password ×3 | `enums.py`, `theme/palette.py`, `markdown/renderer.py` | The literal is `"PASS"` — this framework's outcome vocabulary, not a credential |
| B311 non-crypto RNG | `sdk/helpers/retry.py` | Retry jitter. Not a security use |
| B101 assert | `sdk/helpers/retry.py` | A loop invariant, not input validation |

B105 is skipped project-wide in `pyproject.toml` with the reason recorded, because `PASS`/`FAIL` will
false-positive forever in a tool whose domain vocabulary *is* those words. The other three are
annotated inline, so each justification sits next to the code it excuses rather than in a config file
nobody reads.

---

## 3. Configuration consistency

| File | Validated by | Fails how |
|---|---|---|
| `configs/config.yaml` | pydantic at startup | Fast, with the exact field path |
| `configs/targets.yaml` | pydantic + authorization check | No scan without an authorization record |
| `configs/plugins.yaml` | Written only by `PluginManager` | Single mutation point |
| `configs/analyzer/*.yaml` | `AnalyzerConfigReport` | Reports what was missing rather than guessing |
| `configs/reporting/*.yaml` | Degrades to defaults, **and says so** | Never silently |

No secret appears in any committed configuration file, and there is nowhere in the schema to put
one. Verified by the `Configuration loading` consistency check on every validation run.

---

## 4. Logging consistency

Structured JSON lines by default. Every record carries the scan id where one exists.

The rule that matters: **no log line contains document text, question text, answer text, or a masked
value.** Refusals log a reason code; masking logs a kind and a fingerprint. A control that logged
what it blocked would turn the log into the exfiltration channel it just closed.

`RequestLoggingMiddleware` in the lab applications is the deliberate exception, and VulnerableRAG's
copy documents that its absence of redaction is itself part of the lesson.

---

## 5. Summary

**Release-ready on structure and quality.** Zero dead modules, zero import-time cycles, zero security
findings, six of six architectural contracts machine-enforced, and 1,327 passing tests.

**Two honest gaps**, both in the debt register with estimates: eleven pre-existing mypy errors, and
29 leaf packages without a README.

Neither blocks a v1.0.0 tag. Both are visible rather than buried, which is the standard this project
has held to throughout.
