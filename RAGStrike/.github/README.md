# `.github` — Repository Automation

> **Layer:** CI/CD  ·  **SDD reference:** [SDD §35.2](../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Workflows, issue templates, PR template, and CODEOWNERS. Phase 1 ships the workflow file with the gates wired but the heavy jobs stubbed — the point is that the dependency rule and type checking are enforced from the first commit, before there is any code to violate them.

## Responsibilities

- `workflows/ci.yml` — ruff, black, mypy strict, import-linter, pytest, coverage gate.
- `workflows/` later — `security.yml`, `differential.yml`, `packs.yml`, `docs.yml`, `release.yml`.
- `ISSUE_TEMPLATE/` — bug report, feature request, attack pack proposal.
- `PULL_REQUEST_TEMPLATE.md` — the Definition of Done as a checklist.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `workflows/ci.yml` | Lint, types, layering, tests | 1 |
| `workflows/security.yml` | bandit, pip-audit, CodeQL, gitleaks | 11 |
| `workflows/differential.yml` | Nightly SC1 validation | 10 |
| `CODEOWNERS` | Review ownership | 1 |

## This folder must NEVER contain

- Secrets in workflow files — use repository secrets.
- A workflow that can push to a registry without an explicit tag trigger.
