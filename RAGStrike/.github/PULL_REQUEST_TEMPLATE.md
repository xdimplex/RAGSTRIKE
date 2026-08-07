## What this changes

<!-- One or two sentences. Link the issue it closes. -->

Closes #

## Why

<!-- The problem, not the diff. The diff is visible below. -->

## Type

- [ ] Bug fix
- [ ] New feature
- [ ] Attack pack
- [ ] Target adapter
- [ ] Documentation
- [ ] Refactor (no behaviour change)
- [ ] Breaking change

## Definition of Done

- [ ] Implementation complete — no `TODO` in the merged path
- [ ] Tests added; new public behaviour is covered
- [ ] `mypy --strict` clean
- [ ] `ruff` and `black` clean
- [ ] **`lint-imports` passes** (the dependency rule)
- [ ] Coverage gate met
- [ ] Documentation updated, including the relevant folder `README.md`
- [ ] `CHANGELOG.md` entry added under *Unreleased*
- [ ] No new dependency, or one justified below
- [ ] No secrets, real endpoints, or real personal data in the diff

## Architecture

- [ ] This change respects the layer boundaries in `ARCHITECTURE.md`
- [ ] This change does **not** contradict the SDD, **or** a superseding ADR is included in this PR

<!-- If you added an .importlinter exception, justify it here. It will be scrutinised. -->

## Plugin API

- [ ] No change to `plugins/base/` or `core/contracts/`
- [ ] Changed — `PLUGIN_API_VERSION` bumped to `______` and the compatibility impact noted in CHANGELOG

## For attack packs only

- [ ] Passes the pack conformance suite
- [ ] **Detects on VulnerableRAG** (state which findings)
- [ ] **Produces zero findings on SecureRAG** (false-positive gate)
- [ ] Payloads declare `destructive: false`
- [ ] Technique is publicly documented, with references
- [ ] Ships a remediation catalog entry

## New dependencies

<!-- Name, purpose, why the stdlib is insufficient, and why it belongs in the base install rather
     than an optional extra. "It's convenient" is not a justification. -->

None.
