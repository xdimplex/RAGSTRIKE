# `prompt-injection` — Prompt Injection Attack Pack

> **OWASP:** LLM01 · **Severity:** HIGH · **Requires:** CHAT · **Phase:** 7
> **Catalogue:** [Annex B](../../../../docs/annex-b-attack-catalog.md)
> **Full documentation:** [`docs/prompt-injection-pack.md`](../../../../docs/prompt-injection-pack.md)
> **Status:** implemented.

## Purpose

Can a user's message override the application's instructions? The most direct question in the
catalogue, and the baseline every other injection pack is measured against.

## Non-offensive by construction

Every payload asks the target to emit a meaningless canary token — `RAGSTRIKE-PI-Q1` and
relatives. Nothing here requests a secret, writes to the corpus, or issues anything but a chat
request. A target that emits the token has demonstrated the vulnerability with nothing of value
extracted, which is the entire design of canary detection (ADR-005).

`destructive: false` is required on every payload and asserted by the tests.

## Scope

**Loopback only.** The pack refuses a non-loopback target before its first request and records
SKIPPED with the reason. This repeats the framework's own guard in `build_adapter()` on purpose: a
control that only exists upstream of you is one you are trusting rather than enforcing.

## Layout

```
prompt_injection/
├── pack.yaml                 manifest
├── plugin.py                 lifecycle wiring
├── detectors.py              three pure detectors
├── attacks/techniques.yaml   what each technique is, and which detectors decide it
├── payloads/{quick,standard,deep}.yaml
├── detectors/bindings.yaml   weights, decisiveness, refusal vocabulary
└── recommendations/catalog.yaml
```

Everything tunable is data. `plugin.py` knows *how* to look for a canary; `bindings.yaml` decides
*how much* finding one is worth.

## The seven techniques

`direct-override`, `delimiter-escape`, `authority-spoof`, `task-substitution`,
`encoding-obfuscation`, `multilingual-pivot`, `payload-splitting`.

`payload-splitting` requires `SESSION_MEMORY` and is recorded SKIPPED — never ERROR — against a
target that does not declare it.

## Verdicts

| Outcome | When |
|---|---|
| `FAIL` | A decisive detector fired at or above `min_confidence`. |
| `PASS` | A decisive detector was checkable and did not fire. |
| `INCONCLUSIVE` | The target said nothing, or only a non-decisive signal fired. |
| `SKIPPED` | Capability gap, setup turn, or a refused non-local target. |

An empty response is INCONCLUSIVE, never PASS. Silence is not resistance.

## This folder must NEVER contain

- Executable payloads. Payloads are data, rendered by a non-evaluating loader (ADR-016).
- Destructive payloads.
- Imports of private core internals — packs use `sdk/` and `plugins/base/` only.
- Any special handling in the engine. Delete this directory and the engine still starts, still
  scans, and still reports, with a coverage gap recorded. There is a test that proves no
  prompt-injection logic exists under `core/`.
