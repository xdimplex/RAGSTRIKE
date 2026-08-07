## What this changes

Closes #

## Which profile does this affect?

- [ ] Shared core (`rag/`, `backend/`, `frontend/`) — affects **both**
- [ ] Vulnerable profile only
- [ ] Secure profile only
- [ ] Corpus or documentation

## Checklist

- [ ] `black`, `ruff`, and `mypy` clean
- [ ] Tests added or updated
- [ ] Documentation updated, including the relevant folder `README.md`
- [ ] `CHANGELOG.md` entry added

## The two rules that matter here

- [ ] **No `if profile == ...` branch was added anywhere in `rag/`, `backend/`, or `frontend/`.**
      The profiles differ only in which policies they compose (ADR-009). A branch in shared code
      breaks that guarantee.
- [ ] **Functional parity is preserved.** Both profiles still answer benign queries equivalently. If
      this changes behaviour, it changes it identically for both.

## Safety

- [ ] Nothing binds beyond `127.0.0.1`
- [ ] No real credentials, real personal data, or real company documents added
- [ ] Any new lab secret is synthetic, high-entropy, and canary-tagged

## For a new weakness

- [ ] Added to `docs/vulnerabilities.md` with reproduction steps
- [ ] The corresponding defence exists in the secure profile, or is tracked in a linked issue
