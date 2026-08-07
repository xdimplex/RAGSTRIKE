> ⚠️ **This repository is an intentionally vulnerable application built for security testing.**
> It must never be deployed anywhere reachable. See [`docs/LAB_SAFETY.md`](../docs/LAB_SAFETY.md).

# `docs` — Documentation

> **Profile scope:** repository  ·  **SDD reference:** [SDD §32–33](../../RAGStrike/docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The lab's own documentation, including the containment rules and the vulnerability catalogue. This repository is a teaching artifact as much as a test target, and the documentation is a first-class deliverable rather than an afterthought.

## Responsibilities

- `LAB_SAFETY.md` — containment rules and why the lab binds to loopback only. Read this first.
- `vulnerabilities.md` — the V1–V9 catalogue with reproduction steps.
- `defenses.md` — the SecureRAG control set.
- `the-diff.md` — side-by-side comparison; the executable remediation guide.
- `teaching-guide.md` — exercises for learners.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `LAB_SAFETY.md` | Containment rules | 1 |
| `vulnerabilities.md` | V1–V9 with reproduction steps | 2 |
| `defenses.md` | Control set | 11 |
| `the-diff.md` | Side-by-side | 11 |

## This folder must NEVER contain

- Instructions for deploying this application publicly.
- Attack techniques presented without their corresponding defence — every weakness documented here has its mitigation documented alongside it.
