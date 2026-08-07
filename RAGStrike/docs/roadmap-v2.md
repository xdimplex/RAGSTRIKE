# Roadmap — v2.0

> **Roadmap items only. None of this is implemented, and nothing here is a commitment.**
>
> The authoritative milestone list is [`../ROADMAP.md`](../ROADMAP.md) and
> [`annex-d-risk-roadmap.md`](annex-d-risk-roadmap.md); this document expands the post-v1 section
> with the reasoning behind each item.

---

## Closing the v1 gaps first

Before anything below, the declared-but-unbuilt pieces from v1:

| Item | Why it comes first |
|---|---|
| **The `/api/v1` server** | The dashboard is already a complete client of it. Everything else in the UI is blocked behind this one component |
| **PDF rendering** | Declared, refusing, and the most commonly requested report format |
| **`ragstrike report` CLI** | Report generation has no command-line surface |
| **SecureRAG auth chain** | Authentication, then authorization, then rate limiting — in that order, because each unblocks the next |

---

## v2.0 themes

### Additional evaluation packs

Annex B catalogues twelve; four are built. The remaining eight — indirect injection variants, secret
extraction, PII leakage, context window overflow, hallucination evaluation, excessive agency,
insecure output handling, and model denial of service — are the bulk of the remaining coverage.

*Why it matters:* coverage is reported honestly, so every unbuilt pack is a visible gap in every
report. This is the highest-value work by that measure.

### CI/CD integration

SARIF output for native code-scanning integration, a GitHub Action, and a regression-alerting mode
that compares against a stored baseline.

*Design note:* SARIF is the constraint that matters. Its schema does not map cleanly onto findings
that carry a coverage qualifier, and dropping the qualifier to fit would be exactly the kind of
lossy conversion that turns a careful grade into a misleading one.

### REST API for RAGStrike

The `/api/v1` surface in SDD §22.2. Composition root, SSE progress streaming, and the Pydantic
boundary. Unblocks the dashboard and makes the engine addressable from other tools.

### Multi-target orchestration

Scanning a fleet, with per-target concurrency limits and an aggregate posture view.

*Blocked on:* the scheduler is deliberately pure and I/O-free, so orchestration belongs above it —
a design decision to preserve rather than work around.

### Authentication and multi-tenancy

Everything in v1 assumes one operator on one machine. Multi-tenancy is not a feature that can be
added late: it changes the data model, the authorization story, and what a "scan" belongs to.

### Distributed scanning

Workers pulling from a queue, for corpora too large for one machine.

*Blocked on:* determinism. SC4 requires that the same seed and corpus produce identical results, and
work distributed across workers has to preserve that or the guarantee is lost.

### Container orchestration

Compose files exist as Phase 1 scaffolds and are not CI-exercised. A supported path means images,
health checks, and a documented upgrade procedure.

### Plugin marketplace

A community index. **The blocker is trust, not packaging:** plugins currently run with full process
trust, so a marketplace without subprocess isolation and a capability broker would be a supply-chain
hazard with a search box.

### Regression dashboards

Trend views across scans, with the cross-version comparison refusal already built into the scoring
model surfaced in the UI.

### Enterprise deployment

RBAC, audit logging, SSO, retention policy. Follows multi-tenancy; not meaningful before it.

---

## Deliberately still out of scope

Detection evasion · WAF bypass · rate-limit circumvention · mass or untargeted scanning · any feature
whose primary value is testing systems the operator is not authorized to test.

Recorded here, as in `ROADMAP.md`, so the boundary is not relitigated in every feature discussion.
