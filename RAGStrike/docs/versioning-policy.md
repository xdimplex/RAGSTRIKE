# Versioning, compatibility, and deprecation

> **Current version: 1.0.0** · **Plugin API version: 1.0.0**

---

## Two version numbers, on purpose

| Number | Where | Governs |
|---|---|---|
| **Application version** | `VERSION`, `__version__`, `pyproject.toml`, `CITATION.cff` | The framework as a product |
| **Plugin API version** | `PLUGIN_API_VERSION` | The contract third-party packs are written against |

They move **independently** (ADR-015), and that is the single most important thing on this page.

A patch release of the application — a CLI fix, a report template tweak — must not signal a potential
break to every pack author. If the two were one number, every release would look like it might have
changed the plugin contract, and authors would either re-verify constantly or stop paying attention.
Both outcomes are worse than carrying two numbers.

Packs declare `requires_api` in their manifest. The registry refuses to load an incompatible pack
**before importing its code** — a refusal, with the reason, rather than a crash.

---

## Semantic versioning

`MAJOR.MINOR.PATCH`, applied to the **public surface**: the CLI, the configuration schema, the report
formats, the database schema, and the plugin contract.

| Bump | Means | Examples |
|---|---|---|
| **MAJOR** | A break requiring user action | CLI flag removed; config key renamed; report field removed; migration that is not backward-compatible |
| **MINOR** | Additive, backward-compatible | A new attack pack; a new report format; a new optional config key; a new CLI subcommand |
| **PATCH** | Neither adds nor breaks | Bug fix; docs; performance; internal refactor |

### What is *not* the public surface

Anything under `src/ragstrike/` that no pack, config file, or CLI invocation reaches. Internal
refactors are patch releases even when they are large — `reporters/base/record.py` was added mid-phase
purely to satisfy a layer contract, and nothing outside the package could observe it.

### The scoring model is versioned separately again

Risk weights carry a `scoring_model_version`. **A target that has not changed must not change grade
because RAGStrike was upgraded.** Changing a weight requires bumping that version and a changelog
entry, and trend views refuse cross-version comparison without an explicit recompute.

This is deliberately stricter than semver would require: a weight change is technically
backward-compatible in the API sense and would otherwise slip out in a patch.

---

## Compatibility policy

### What v1.0.0 commits to

For the life of the 1.x line:

- **The CLI stays.** Commands and flags may be added; existing ones keep working. Removal needs 2.0.
- **Configuration keys stay.** New keys may be added with defaults; existing ones keep their meaning.
  A key whose *meaning* changes is a break even if its name does not.
- **Report field names stay.** Fields may be added. A consumer parsing `risk_score` today parses it
  in 1.9.
- **The plugin contract stays.** A pack written against Plugin API 1.0 loads on any 1.x framework.
- **Migrations are append-only.** Never reordered, never edited in place. A database that applied
  migration 3 sees the same migration 3 forever.

### What v1.0.0 does *not* commit to

- **Internal module paths.** `from ragstrike.analyzers.rules.engine import ...` may move. Use the
  package-level exports.
- **Findings themselves.** Detector tuning changes what is found — that is the product improving, not
  a compatibility break. Scoring *weights* are the versioned part.
- **The `/api/v1` surface**, which does not exist yet. When it ships it carries its own `v1` in the
  path, and a break there requires `/api/v2` rather than a framework major bump.
- **Anything documented as declared-but-unimplemented** in [`limitations.md`](limitations.md). A
  placeholder that starts working is a MINOR, not a break.

### Python

3.11+ for the 1.x line. Raising the floor is a MINOR (it does not break the API, but it does need a
changelog entry and a note in the release). Dropping to a *lower* floor never happens.

---

## Deprecation policy

Nothing in 1.x is removed without going through this, in order:

**1. Announce.** The release notes name what is deprecated, what replaces it, and the earliest version
it can be removed in. A deprecation with no replacement named is not a deprecation, it is a warning
that something will break.

**2. Warn at runtime.** A `DeprecationWarning` at the point of use, saying what to use instead. Not
at import — a warning nobody triggers is a warning nobody sees.

**3. Wait.** At least **two MINOR releases**, and at least **90 days**. Whichever is longer.

**4. Remove in the next MAJOR.** Never in a MINOR or PATCH, however long the deprecation has run.

### The exception, stated so it cannot be abused

A **security defect** in a shipped default may be corrected in a MINOR release without the full
deprecation window — for example, if a safety default turned out to be permissive.

Three conditions, all required: the change makes the default *more* restrictive; the release notes
lead with it; and the old behaviour remains reachable by explicit configuration where that is safe.

Making the local-only target policy stricter would qualify. Renaming a CLI flag never would,
regardless of how much better the new name is.

---

## Release tags

```
v1.0.0
```

Annotated tags, on the commit whose `VERSION` file matches. The tag is the release; `pyproject.toml`
is bumped in the commit being tagged, not before — a version bump on an untagged commit implies a
distribution history that does not exist.

Pre-releases use `v1.1.0-rc.1`. The 1.0.0 release candidate was carried as `0.3.0` precisely so the
1.0.0 number was not spent before the audit that justified it.

---

## Checklist for any version bump

1. `VERSION`, `__version__`, `pyproject.toml`, `CITATION.cff` — all four, same value
2. `CHANGELOG.md` entry
3. `RELEASE_NOTES.md` if MINOR or MAJOR
4. `PLUGIN_API_VERSION` — **only** if the plugin contract actually changed
5. `scoring_model_version` — **only** if a weight changed
6. Full gate: `pytest && lint-imports && ruff check . && black --check .`
7. `python -m validation.runner --checks-only`
8. Tag
