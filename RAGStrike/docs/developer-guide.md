# Developer guide

> Extending RAGStrike. For running scans, see [`user-guide.md`](user-guide.md).

---

## The dependency rule

Higher layers import lower ones; never the reverse. It is enforced by `lint-imports` as a **merge
gate**, not a review convention — six contracts in `.importlinter`:

| Contract | Says |
|---|---|
| Clean Architecture layers | The full stack, cli/api/dashboard at the top, utils at the bottom |
| Domain purity | `models/` imports nothing from `ragstrike` |
| **Dashboard isolation** | The dashboard never imports the engine — **including indirectly** |
| **Scoring determinism** | `core.scoring` cannot reach a model, an adapter, a database, or httpx |
| Utils purity | `utils/` depends on nothing |
| Scheduler purity | The scheduler performs no I/O |

Two notes from experience:

**Same-row modules are siblings and may not import each other.** `cli | api | dashboard` means the
dashboard cannot import the API either.

**A function-level import is still an import.** `grimp` reads the whole AST, so deferring an import
inside a function does not evade a contract. When Phase 11 hit this, the fix was structural — a new
type on the lower layer — not a suppression.

---

## Adding an attack pack

1. `plugins/<name>/pack.yaml` — the manifest. Discovery is manifest-first
2. `plugins/<name>/plugin.py` — a class implementing the nine-method lifecycle
3. Payloads, detectors, and recommendations as **data**, never as code
4. `ragstrike plugins validate <name>`

No registration anywhere in the engine. A test asserts no plugin name appears in engine code, so the
zero-core-edit promise cannot quietly stop being true.

Full walkthrough: [`plugin-development.md`](plugin-development.md), [`sdk-guide.md`](sdk-guide.md),
[`plugin-lifecycle.md`](plugin-lifecycle.md).

---

## Adding a report format

Subclass `BaseRenderer`, set `name`/`extension`/`media_type`, implement `render`, register it. A test
parses `report_engine.py` and asserts no format name appears as a code-level string literal outside
the default-registry helper — so "adding a format changes no existing code" stays checkable.

---

## Adding an analyzer rule

Rules are YAML in `configs/analyzer/rules.yaml`. They are **data, never evaluated** — a rule file is
something an operator edits, and a rule language that could execute would turn tuning into a
code-execution surface.

---

## Adding a dashboard page

A `Route` in `navigation/routes.py` plus a module with one `render(context)`. The sidebar, router,
quick actions, and search all read the registry, so nothing else changes.

Two rules: pages never build requests (services do), and nothing outside `theme/` contains a colour
literal — a test enforces both.

---

## The gate

```bash
pytest && lint-imports && mypy src && ruff check . && black --check .
```

Plus, for a release:

```bash
python -m validation.runner --checks-only
```

---

## Conventions worth knowing

**`INCONCLUSIVE` is a first-class outcome.** If a plugin cannot tell, it says so. Returning PASS on
absence of evidence is the failure mode the whole analyzer design exists to prevent.

**Migrations are append-only.** Never reorder or edit one in place.

**Scores are arithmetic.** Nothing in `core.scoring` may call a model — a contract enforces it.

**Recommendations are retrieved, not generated.** From a reviewed catalog.

**Evidence is redacted, not omitted.** A finding without evidence is an assertion.

**Every error carries a hint.** A failure with no next step is a dead end.

---

## Where things live

| Path | Holds |
|---|---|
| `src/ragstrike/core/` | Orchestrator, executor, scoring, config, contracts |
| `src/ragstrike/plugins/` | The plugin framework: discovery, registry, lifecycle |
| `src/ragstrike/sdk/` | The developer kit third-party pack authors use |
| `src/ragstrike/attacks/` | First-party packs |
| `src/ragstrike/analyzers/` | Raw results become standardized findings |
| `src/ragstrike/reporters/` | One model, N renderers |
| `src/ragstrike/dashboard/` | Streamlit UI — never imports the engine |
| `validation/` | The validation harness. Development tooling |
| `docs/annex-c-adrs.md` | Twenty ADRs. **If a decision is not recorded there, it has not been made** |
