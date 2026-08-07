# Technical debt register

> Every entry: what it is, what it costs, why it was not fixed, and what fixing it takes.
>
> Debt that is written down is a decision. Debt that is not is a surprise.

Nothing here blocks the v1.0.0 tag. All of it is visible in
[`audit-report.md`](audit-report.md) and [`release-checklist.md`](release-checklist.md).

---

## D-01 — Eleven mypy errors in pre-Phase-10 code

**Severity:** Low · **Effort:** ~2 hours · **Blocked by:** phase discipline

```
2  cli/output/console.py               missing parameter annotations
3  cli/main.py                         missing parameter annotations + unreachable
1  core/orchestrator/scan_engine.py    missing parameter annotation
2  plugins/loader/loader.py            incompatible assignment, missing type arguments
1  plugins/registry/plugin_manager.py  missing parameter annotation
1  database/repositories/plugin_repository.py  missing type arguments
```

**Cost.** `mypy src` is not a clean gate, so the gate is run with a known-failure list — the exact
situation where a *new* error hides among old ones.

**Why not fixed.** Every phase brief forbids modifying previous phases. These annotations live in
Phase 3–5 code.

**Fix.** Annotate the parameters; delete the two unreachable branches after confirming they are
genuinely unreachable. Then remove the note from the release checklist and make `mypy src` a hard
gate.

---

## D-02 — 29 packages without a README

**Severity:** Low · **Effort:** ~3 hours

Mostly leaf subpackages under `analyzers/` and `dashboard/` — `analyzers/scoring`,
`dashboard/navigation`, `dashboard/state`, and similar.

**Cost.** Navigation, not comprehension: every module in them has a docstring and every parent
package is documented. A newcomer opening one of these directories has to read code to learn its
boundary.

**Fix.** One README per package stating the responsibility **and what the package must never
contain**. The second half is the part that has caught real mistakes elsewhere in this tree.

---

## D-03 — `/api/v1` is a scaffold

**Severity:** High · **Effort:** ~2 days · **Tracked in:** [`limitations.md`](limitations.md)

Routing exists; handlers do not.

**Cost.** The dashboard cannot display live scan results. It shows `BACKEND OFFLINE`, or demo
fixtures clearly labelled as such (ADR-021). Every other consumer of the framework must use the CLI.

**Why not fixed.** Implementing it inside a later phase would merge phases, which every brief
forbids.

**Fix.** Implement the handlers against the contract the dashboard already codes to. **No dashboard
change is required** — that was the point of the transport Protocol.

---

## D-04 — No full differential scan has been completed

**Severity:** High · **Effort:** hours of wall clock, no code · **Tracked in:**
[`validation-results.md`](validation-results.md)

**Cost.** The framework's central claim — that it separates a vulnerable RAG from a hardened one —
is **designed and instrumented but not yet demonstrated end to end**. The validation summary records
this rather than implying otherwise.

**Why not.** A local model on CPU takes roughly 5–40 seconds per payload; a complete run across both
targets is a multi-hour job, and no phase had room for it.

**Fix.** Run it. `python -m validation.runner --targets vulnerable-rag secure-rag` with both lab
applications up and identically seeded, then commit the resulting summary. No code changes expected —
and if any are needed, that is itself the most valuable finding available.

---

## D-05 — PDF export is declared and refuses

**Severity:** Low · **Effort:** ~4 hours · **Tracked in:** ADR C.1

`formats()` reports `pdf: false` and `export_all` skips it.

**Cost.** A user reading the format list sees a format they cannot use.

**Why it is this way rather than removed.** The renderer registry makes PDF additive, and a declared
capability that refuses honestly is better than a silent HTML file with a `.pdf` extension.

**Fix.** Add a renderer. Nothing else changes.

---

## D-06 — Plugins are not sandboxed

**Severity:** Medium · **Effort:** large · **Tracked in:** ADR C.1, roadmap R-07

Installing an attack pack grants it the trust of installing a Python package, because it *is*
installing a Python package.

**Cost.** A hostile third-party pack can do anything the user can.

**Why not fixed.** OS-level isolation is a subsystem, not a patch. The trust model documents the
situation plainly instead of implying protection that does not exist.

**Fix.** Subprocess isolation with a capability-restricted channel. Roadmap item.

---

## D-07 — Consistency checks encode API shapes by hand

**Severity:** Low · **Effort:** ~1 hour

Two of the ten checks in `validation/runner/consistency.py` originally asserted APIs that did not
exist — a wrong arity for `build_engine`, and a log directory in the wrong place. Both were caught
and corrected, but the underlying fragility remains: the checks describe the API from outside it.

**Cost.** A refactor can make a check assert something stale, and a stale check either fails
spuriously or passes vacuously.

**Fix.** Derive the assertions from `inspect.signature` where the shape is what matters, and keep
hand-written assertions only where the *value* is the point.

---

## What is deliberately not here

**"Add more attack packs."** That is a roadmap item, not debt — the plugin contract makes it
additive by design.

**"The dashboard uses Streamlit."** A recorded decision with its alternatives (SDD §UI), not an
accident to be paid off.
