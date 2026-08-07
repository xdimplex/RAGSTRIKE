# Architecture

## The dependency rule

Four layers. Dependencies point **inward, only**.

```
┌─────────────────────────────────────────────┐
│  cli   ·   dashboard   ·   api              │   interface
├─────────────────────────────────────────────┤
│  core  ·  analyzers  ·  reporters           │   application
├─────────────────────────────────────────────┤
│  plugins  ·  adapters  ·  database          │   adapters
├─────────────────────────────────────────────┤
│  models  ·  config  ·  logging              │   domain
└─────────────────────────────────────────────┘
```

**This is machine-enforced**, not a diagram. Six `import-linter` contracts fail the build on
violation. `lint-imports` failing is a design failure, not a lint failure, and the fix is essentially
never to edit the contract file.

Two consequences that are easy to trip over:

- **Siblings on one row may not import each other.** They are peers, not a stack.
- **Indirect chains count.** `reporters` importing `analyzers` which imports `models` breaks a
  contract even though no single import looks wrong. This actually happened, and produced a real
  refactor.

A function-level import does not escape the check: `grimp` reads the AST, not the runtime.

## Plugins

**A new attack pack requires zero edits to the framework.** Enforced by a test that parses every
module and asserts no plugin name appears in engine code.

```
plugins/my-pack/
├── metadata.yaml      read BEFORE any code is imported
├── plugin.py
└── payloads/*.yaml    data, never Python
```

The manifest comes first (ADR-003): the registry decides compatibility and capability fit before
importing, so an incompatible pack is *refused with a reason* rather than imported and crashed.

Payloads are data (ADR-016) so that an attack corpus can be security-reviewed by someone who does not
read Python, and so that a scan is reproducible.

### The lifecycle

`metadata` → `validate` → `setup` → `payloads` → `execute` → `analyze` → `report` → `cleanup` →
`health`

**`payloads()` is deterministic** — that is what makes a scan reproducible. **`analyze()` is pure** —
no network, no clock, no randomness — which is what makes a verdict explainable and lets recorded
evidence be re-analysed offline without re-attacking anything.

## Targets

One abstract interface with capability negotiation (ADR-008). A pack needing a capability the target
lacks is skipped **with the skip recorded in Coverage**, never silently dropped.

## Analysis and scoring

Raw plugin results become standardized `Finding` objects. Signals aggregate by weighted noisy-OR with
a capped LLM judge (ADR-006) — capped because a judge that can dominate a verdict makes the verdict
unreproducible.

Weights carry a `scoring_model_version`. **A target that has not changed must not change grade because
RAGStrike was upgraded.**

## Reporting

One model, N renderers. Every computation happens once, in the builders; a renderer only chooses
presentation. HTML, Markdown, and JSON therefore *cannot* disagree about the same scan — neither of
them computes anything.

## The dashboard

An HTTP client of `/api/v1`, never an importer of the engine (ADR-010). Access goes through a
transport Protocol, so the interface is complete against an API that does not answer yet — and will
need no changes when it does.

## The lab

**VulnerableRAG** and **SecureRAG**: identical corpus, identical API surface, opposite security
posture. SecureRAG adds a five-hook policy chain — `on_ingest`, `on_chunk`, `on_context_assembly`,
`on_prompt_build`, `on_response`.

Surface parity is checked by reading `/openapi.json` from both and failing on divergence. An earlier
version of that test walked an in-process route list, silently found nothing, and could never fail —
**a compatibility test that cannot fail is worse than none**.

## Further reading

[SDD](../docs/SDD.md) · [Annex A: directory structures](../docs/annex-a-directory-structures.md) ·
[Annex C: 24 ADRs](../docs/annex-c-adrs.md) · [Audit report](../docs/audit-report.md)
