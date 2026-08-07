# Maintenance guide

For whoever owns this repository next. What to run, what to watch, and which invariants must not be
broken by a well-meaning refactor.

---

## Routine

| When | Do |
|---|---|
| Every PR | The gate (below) |
| Every dependency bump | Gate + `pip-audit` |
| Monthly | Re-read [`technical-debt.md`](technical-debt.md); close or re-estimate |
| Before any tag | [`release-checklist.md`](release-checklist.md), in order |
| Quarterly | Re-run the audit; compare against [`audit-report.md`](audit-report.md) |

## The gate

```bash
pytest && lint-imports && ruff check . && black --check . && mypy src
```

`mypy src` has 11 known failures ([D-01](technical-debt.md)). Everything else must be clean.

```bash
bandit -c pyproject.toml -r src/ragstrike
python -m validation.runner --checks-only
python -c "from validation.runner.audit import collect; print(collect().to_dict())"
```

---

## The invariants

Six architectural contracts are machine-enforced by `import-linter`. **`lint-imports` failing is not
a lint failure — it is a design failure**, and the fix is almost never to edit `.importlinter`.

Two rules that are easy to violate by accident:

**Siblings on the same row of a layer contract may not import each other.** They are peers, not a
stack.

**A function-level import is still an import.** `grimp` reads the AST; deferring an import to a
function body hides it from the runtime, not from the contract. This is exactly how
`reporters.service` would break contract 3 — indirectly, via `analyzers` → `models`.

Beyond the linter:

- **The dashboard never imports the engine** (ADR-010). All access goes through `BackendTransport`.
- **`MIGRATIONS` is append-only.** Never reorder, never edit in place. A database that applied
  migration 3 must see the same migration 3 forever.
- **No plugin slug appears in framework code.** A test enforces it. If a pack needs a special case in
  the engine, the contract is wrong — not the test.
- **`analyze()` stays pure.** No network, no clock, no randomness. Reproducible verdicts are what the
  whole scoring model rests on.
- **No log line contains document, question, or answer text.** A control that logged what it blocked
  would become the exfiltration channel it just closed.

---

## Changing scoring

Risk weights carry `scoring_model_version`. Changing a weight **requires** bumping it, plus a
changelog entry.

**A target that has not changed must not change grade because RAGStrike was upgraded.** Trend views
refuse to compare across scoring versions without an explicit recompute. This is stricter than semver
requires, because a weight change is technically backward-compatible and would otherwise ship
invisibly in a patch.

## Changing the plugin contract

`PLUGIN_API_VERSION` moves independently of `__version__` (ADR-015). Bump it **only** when the
contract actually changed — a bump every release teaches pack authors to ignore it, which defeats the
mechanism.

## Adding a migration

Append. Never edit. Test against a database at the previous version, not only a fresh one.

## Adding a dependency

Justify it in [`dependency-summary.md`](dependency-summary.md), check the licence against
[`third-party-attribution.md`](third-party-attribution.md), and pin it. A dependency that is easier to
add than to justify is how supply chains grow.

---

## Amending the design

The SDD is the source of truth. Changing a decision requires a **superseding ADR appended to
[Annex C](annex-c-adrs.md)** — never an edit to an existing one. ADR-022 amends ADR-009 that way, and
ADR-009's reasoning remains readable even though its conclusion no longer holds.

## Reviewing a contributed attack pack

[`plugin-review-checklist.md`](plugin-review-checklist.md). The section to read twice is *Honesty* —
a pack returning PASS when it simply failed to detect anything is the most common and most damaging
defect, and it looks like a working pack.

Run any new pack against **SecureRAG**. If it fires there too, it is not measuring what it claims.
