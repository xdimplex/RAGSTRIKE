# `examples/ci_integration` — CI Examples

> **Layer:** documentation · **SDD:** [`docs/SDD.md`](../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Runnable pipeline configurations that gate a build on posture, using CLI exit codes.

## Responsibilities

- GitHub Actions and GitLab CI examples.
- Demonstrate `--fail-on HIGH` and the distinct exit codes, so a pipeline can tell an insecure application from a misconfigured scanner.

## Files that will exist here later

- `github_action.yml`
- `gitlab_ci.yml`

## This folder must NEVER contain

- Examples that do not run.
- Real credentials or real endpoints.
