# Known limitations

> Stated plainly. A security tool whose limits live only in its author's head gets trusted for things
> it cannot do.

---

## Not implemented

### The REST API

`src/ragstrike/api/` is still the Phase 1 scaffold. The dashboard is a complete client written
against the `/api/v1` contract in SDD §22.2, so without a server every page shows an honest
`BACKEND OFFLINE` state. Nothing else depends on it: the CLI reaches the full engine directly.

**Impact:** the dashboard cannot show live data. Use demo mode to review the interface.

### PDF reports

Declared and refusing. HTML, Markdown, and JSON render; `formats()` reports `pdf: false`, and
`render_all`/`export_all` skip it rather than producing something that opens broken.

### Rate limiting, authentication, authorization in SecureRAG

Declared and excluded from the control chain by construction. `GET /health` names them under
`warning` rather than `security_policies`, because a control listed as active but doing nothing tells
an operator they are covered when they are not.

### A `ragstrike report` CLI command

Reports are generated through the reporting engine's Python API. There is no command for it yet.

---

## Scope constraints

**Local deployment only.** Single operator, single machine. There is no multi-tenancy, no
authentication on any RAGStrike surface, and no concurrency control beyond one scan at a time.

**Localhost-only by default,** and deliberately hard to change: two independent settings, not one.

**Nine plugins across four packs** — prompt injection, prompt leakage, context poisoning, and five
evaluation plugins. Annex B catalogues twelve packs; the rest are not built.

**One adapter.** `fastapi`, configuration-driven. OpenAI-compatible, LangChain, and LlamaIndex
adapters are designed and not built.

---

## Methodological limits

**Detection is pattern- and canary-based.** Canaries are reliable — a token that could only have come
from the system prompt is strong evidence. Pattern matching over natural language is not, and is
defeated by rephrasing. The framework reports confidence and caps it when a detector is
uncalibrated, rather than presenting every match as equally certain.

**Coverage is not completeness.** 100% coverage means every case the installed packs define was
executed. It says nothing about weaknesses no pack tests for.

**Cross-session persistence cannot be established from outside.** The context-poisoning pack returns
INCONCLUSIVE rather than guessing.

**Citation grounding checks retrieval, not entailment.** SecureRAG verifies a cited source was
retrieved, not that it supports the claim.

**Single-sample performance numbers.** No warm-up, no repetition, one machine. Useful for order of
magnitude and for catching a regression that changes one; not for fine-grained comparison.

---

## Validated, and not

**Validated:** every subsystem in isolation and in composition, through 1300+ tests, ten consistency
checks, and a benchmark suite run against the live lab pair.

**Not validated:** behaviour against any RAG application other than the two in this lab; behaviour
under concurrent scans; behaviour with a model other than Qwen3; long-term database growth.

---

## Accepted risks

**Plugins run with full process trust.** v1 does not sandbox at the OS level. Declaring permissions
in the manifest makes intent auditable, which is weaker than enforcement. Installing a pack is
equivalent to installing any Python package: subprocess isolation is a v2 item.

**The lab corpus contains synthetic canaries.** They are high-entropy and clearly labelled so a real
leak can never be confused with a lab artifact — but both applications must stay on loopback.

**`RAGSTRIKE_LAB_ACK=1` is a speed bump, not a control.** Baked into a shell profile or an image, the
gate is defeated.
