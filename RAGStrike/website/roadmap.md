# Roadmap

**Nothing on this page is implemented.** It restates
[`../docs/roadmap-v2.md`](../docs/roadmap-v2.md) and Annex D for a public audience; those are
authoritative.

---

## First, finish what is started

Ahead of any new feature, in order:

**1. Complete the differential run.** The framework's central claim is instrumented but not yet
demonstrated end to end. No code needed — hours of wall clock. [D-04](../docs/technical-debt.md).

**2. Implement `/api/v1`.** The handlers the dashboard already codes against. No dashboard change
required. [D-03](../docs/technical-debt.md).

**3. Clear the recorded debt.** Eleven mypy errors, 29 missing package READMEs. Small, known, costed.

A project that ships new features over an unrun validation suite is a project whose claims stop
tracking its evidence.

---

## Then

| | Why |
|---|---|
| **Plugin sandboxing** (R-07) | Subprocess isolation with a capability-restricted channel. The largest gap between what a user might assume and what is true |
| **SARIF output** | CI integration. Blocked on nothing but priority |
| **PDF rendering** | The registry already makes it additive |
| **More attack packs** | Additive by design — chunk-boundary, embedding-inversion, multi-turn |
| **Agentic target support** (LLM06) | Deferred to v2: testing excessive agency needs an action-side sandbox, or the test causes the damage it is testing for |
| **PostgreSQL backend** | The repository interfaces are already the seam |
| **Distributed execution** | ADR-018 records the seam; no current requirement |

## Deliberately not planned

**A hosted service.** This tool is pointed at systems people own, and a hosted version changes that
relationship in ways the safety model is not designed for.

**Automatic remediation.** Recommendations come from a versioned catalog and name changes a human
makes. A tool that edits a system it just attacked is a tool with two jobs and no separation between
them.

**A GUI attack builder.** Payloads are data so they can be reviewed. A builder that generates them
interactively would put the reviewable artifact behind a UI.

---

Roadmap items are not commitments. Anything above may be reordered or dropped; anything dropped will
be recorded as dropped rather than quietly removed.
