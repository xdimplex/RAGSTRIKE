# Features

---

## Attack packs

**Three offensive packs.**

| Pack | Tests |
|---|---|
| `prompt-injection` | Instructions smuggled through retrieved context |
| `prompt-leakage` | System prompt and configuration extraction |
| `context-poisoning` | Corpus documents that change downstream answers |

**Five evaluation packs** — non-offensive, measuring behaviour rather than attacking:
`prompt-boundary`, `context-separation`, `instruction-priority`, `source-attribution`,
`retrieval-consistency`.

Plus `dummy-attack`, a diagnostic pack that verifies the harness itself reaches a target — nine
discovered packs in total.

Nine further packs from the Annex B catalog are **declared as directories and not implemented**
(`indirect-prompt-injection`, `secret-extraction`, `pii-leakage`, `role-override`,
`context-injection`, `context-window-overflow`, `retrieval-integrity`, `citation-verification`,
`hallucination-evaluation`). Empty, and listed here as empty.

Every pack maps to OWASP LLM Top 10, MITRE ATLAS, and CWE where an identifier exists.

## The differential

The feature that makes the rest checkable: run the same packs against a vulnerable target and a
hardened one.

**A pack that fires on both is not measuring its control.** Without a hardened reference, a false
positive is indistinguishable from a finding, and no amount of report polish fixes that.

## Reporting

HTML · Markdown · JSON. Ten sections: cover, executive summary, risk breakdown, category summary,
detailed findings, evidence, recommendations, statistics, timeline, chart data.

- **The risk arithmetic is printed**, so a reader can reproduce it by hand
- **Every finding names its detector** — request, response, rule
- **Coverage sits beside the grade**
- **Recommendations come from a versioned catalog** (ADR-019), never generated at runtime, so the
  same finding never produces different advice on different days

PDF is declared and **refuses** rather than emitting HTML with the wrong extension.

## Evidence

Immutable, with an offline replay harness (ADR-012). Recorded evidence can be re-analysed after a
detector change **without re-attacking the target** — which is what makes detector work fast enough
to do properly.

Redaction happens in the pipeline, not at call sites (ADR-013). A call site that forgets is the
normal failure mode, so there are no call sites to forget.

## Safety

- **Localhost only by default.** Rejecting anything else
- **Authorization is a persisted record** (ADR-017), not a run-time checkbox
- **No pack writes to a target**
- **No log line contains document, question, or answer text.** A control that logged what it blocked
  would become the exfiltration channel it just closed

## Interfaces

**CLI** — the complete surface; everything works here.

**Dashboard** — nine Streamlit pages. An HTTP client by design (ADR-010); currently reports
`BACKEND OFFLINE` because `/api/v1` is a scaffold, or serves clearly-labelled demo fixtures.

**Database** — SQLite via the repository pattern, no ORM. Migrations are append-only.

## Extensibility

**A new attack pack needs zero framework edits**, enforced by a test. Same for a new target adapter,
a new report renderer, and a new detector.

## Quality

| | |
|---|---|
| Tests | 1,327 passing |
| Architectural contracts | 6 of 6, machine-enforced |
| Import-time circular imports | 0 |
| Dead modules | 0 |
| Security findings (bandit) | 0 |
| Modules · code lines | 251 · 19,805 |
| Known mypy errors | 11, recorded not suppressed |

The last row is the one worth noticing. See [ADR-024](../docs/annex-c-adrs.md) and the
[technical debt register](../docs/technical-debt.md).

## Not yet

`/api/v1` handlers · PDF rendering · plugin sandboxing · SARIF · a completed full differential run.

[`limitations.md`](../docs/limitations.md) is authoritative.
