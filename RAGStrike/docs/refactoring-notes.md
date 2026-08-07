# Refactoring notes

Structural changes made during the pre-release audit, and — more usefully — the ones deliberately
**not** made.

---

## Made

### `reporters/base/record.py` extracted

The reporting service needed the finding shape without importing `analyzers`, which would have broken
layer contract 3 indirectly (`reporters` → `analyzers` → `models`). Verified empirically with a probe
module before writing a line of the fix.

Nothing outside the package can observe the change — which is why it is a patch-level refactor by the
[versioning policy](versioning-policy.md), despite touching several files.

### Escaping moved to a single place

`components/html.py` escaped in both `style()` and `tag()`, producing `&amp;quot;` in generated CSS.
The fix was to escape **once**, in `tag()`, and to document at the `style()` docstring that it does
not escape.

The general lesson: escaping applied defensively at two layers is not twice as safe, it is broken.

### Bandit justifications moved to the code

Six findings, all false. Five are annotated at the site with the reason; only B105 is skipped
project-wide, because `PASS` and `FAIL` are this framework's outcome vocabulary and will
false-positive forever.

A justification in a config file is read by nobody. A justification on the line is read by whoever
touches the line next.

### The audit cycle detector, three times

32 cycles → 1 → 0. Documented in [`audit-report.md`](audit-report.md) and in the module docstring.
Kept as a worked example because the wrong versions were both plausible.

---

## Deliberately not made

### The 11 mypy errors

Fixing them means editing Phase 3–5 code, which the phase discipline forbids. Recorded as
[D-01](technical-debt.md) with an estimate instead. See ADR-024.

### Splitting `scan_engine.py`

It is long. It is also the one place where orchestration order is visible in a single read, and
splitting it would trade a real property for a metric.

**Length is not by itself a defect.** Split it when a *second* reason appears.

### Unifying the two lab applications

ADR-009 argued for one codebase; the owner chose two repositories; ADR-022 records the amendment and
the parity suite that mitigates it. Re-merging now would discard a decision that was made
deliberately — that is a design conversation, not a refactor.

### Deduplicating the target-validation logic

Similar-looking validation exists in the CLI, the dashboard service, and the config loader. They
*look* like duplication and are not: each validates at a different boundary, with different failure
modes and different messages.

**Merging them would create a shared dependency between three layers to save perhaps twenty lines**,
and the layer contract would rightly reject it.

---

## The standard applied throughout

A refactor must either **remove a real constraint** or **make an invariant enforceable**. "Cleaner"
is not a reason, and neither is a metric moving. Every change above satisfies that test; every
omission above fails it.
