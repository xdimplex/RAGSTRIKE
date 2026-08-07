# Plugin index

**Nine packs discovered**, all enabled by default. Verify against your install:

```bash
ragstrike plugins
```

---

## Attack packs — 3

Offensive. They send payloads and look for a weakness.

| Slug | Category | Severity | Requires | Doc |
|---|---|---|---|---|
| `prompt-injection` | `prompt_injection` | HIGH | CHAT | [→](prompt-injection-pack.md) |
| `prompt-leakage` | `prompt_leakage` | HIGH | CHAT | [→](prompt-leakage-pack.md) |
| `context-poisoning` | `context_poisoning` | HIGH | CHAT, RETURN_CHUNKS | [→](context-poisoning-pack.md) |

They live in `src/ragstrike/attacks/`, each with `pack.yaml`, `plugin.py`, `detectors.py`, tiered
`payloads/` (`quick` · `standard` · `deep`), and a `recommendations/catalog.yaml`.

**First-party packs load through the same public entry-point group third parties use** — so the
extension path cannot silently rot. If it breaks, the shipped product breaks first.

## Evaluation packs — 5

Non-offensive. They measure behaviour. [`evaluation-plugins.md`](evaluation-plugins.md).

| Slug | Severity | Requires | Measures |
|---|---|---|---|
| `prompt-boundary` | HIGH | CHAT | Whether instructions and retrieved text are delimited |
| `context-separation` | HIGH | CHAT | Whether retrieved content is kept out of the instruction region |
| `instruction-priority` | HIGH | CHAT | Whether document text can outrank the system prompt |
| `source-attribution` | MEDIUM | CHAT, RETURN_CHUNKS | Whether answers name their sources |
| `retrieval-consistency` | LOW | CHAT, RETURN_CHUNKS | Whether retrieval is stable across paraphrases |

In `plugins/`, discovered from the filesystem.

## Diagnostic — 1

| Slug | Severity | Purpose |
|---|---|---|
| `dummy-attack` | INFO | Proves the harness reaches the target |

**A FAIL from this one means the harness is broken, not the target.** Run it first when a scan
produces something surprising.

## Declared and not implemented — 9

Directories exist under `src/ragstrike/attacks/` with no implementation. They come from the Annex B
catalog of twelve and are listed here so the gap is visible rather than discovered:

`indirect-prompt-injection` · `secret-extraction` · `pii-leakage` · `role-override` ·
`context-injection` · `context-window-overflow` · `retrieval-integrity` · `citation-verification` ·
`hallucination-evaluation`

Techniques and mappings for all twelve are specified in
[`annex-b-attack-catalog.md`](annex-b-attack-catalog.md). **The specification exists; the code does
not.**

## Capabilities

A pack declares what it needs. A target lacking it means the pack is **SKIPPED with a recorded
reason**, and the skip appears in the report's Coverage section (ADR-020) — never a silent omission.

| Capability | Means |
|---|---|
| `CHAT` | The target answers questions |
| `RETURN_CHUNKS` | It returns the chunks it retrieved |
| `INGEST` | It accepts documents |

## Writing your own

Three files, **zero framework edits** — enforced by a test that fails if a plugin slug appears in
engine code.

[`../examples/custom_pack/`](../examples/custom_pack/) is a working pack ·
[`../examples/custom_plugin/`](../examples/custom_plugin/) explains it ·
[`plugin-checklist.md`](plugin-checklist.md) before you ship.
