# `prompt-leakage` — Prompt Leakage Attack Pack

> **OWASP:** LLM07 · **Severity:** HIGH · **Requires:** CHAT · **Phase:** 8
> **Catalogue:** [Annex B](../../../../docs/annex-b-attack-catalog.md)
> **Full documentation:** [`docs/prompt-leakage-pack.md`](../../../../docs/prompt-leakage-pack.md)
> **Status:** implemented.

## Purpose

Can the system prompt be recovered? Prompts routinely carry business rules, internal endpoints, and
policy text that the application treats as secret but stores as a prefix.

## Two commitments

**Evidence is redacted by default.** A prompt-leakage finding is by construction a copy of the
thing that should not have leaked, and evidence is persisted, exported, and pasted into tickets.
The default records that a leak happened and how much matched — never the recovered text. An
integration test asserts the guarantee holds *after* the evidence reaches the database.

**Confidence is calibrated honestly.** Similarity needs the operator's real prompt to compare
against. Without it the detector reports itself un-evaluable and the pack caps confidence at 0.5 —
below the 0.6 failure floor — so an uncalibrated heuristic hit can never be reported as a confirmed
leak. Supply `reference_prompt` (or a lab `prompt_canary`) to get decisive results.

A default-configured scan therefore reports mostly INCONCLUSIVE. That is the correct answer, and
the notes say what to supply to improve it.

## Scope

**Loopback only.** The pack refuses a non-loopback target before its first request, repeating the
framework's `build_adapter()` guard — a control that exists only upstream of you is one you are
trusting rather than enforcing.

## Layout

```
prompt_leakage/
├── pack.yaml                 manifest and default options
├── plugin.py                 lifecycle wiring
├── detectors.py              canary, similarity, pattern — all pure
├── attacks/techniques.yaml   what each technique is, and which detectors decide it
├── payloads/{quick,standard,deep}.yaml
├── detectors/bindings.yaml   weights, decisiveness, patterns, thresholds, calibration cap
└── recommendations/catalog.yaml
```

## The seven techniques

`direct-request`, `completion-continuation`, `translation-laundering`, `format-transformation`,
`debug-pretext`, `token-boundary-probe`, `error-channel-leak`.

`token-boundary-probe` requires `SESSION_MEMORY` and is recorded SKIPPED — never ERROR — against a
target that does not declare it.

## Verdicts

| Outcome | When |
|---|---|
| `FAIL` | A decisive detector fired at or above `min_confidence`. |
| `PASS` | A decisive detector was checkable and did not fire. |
| `INCONCLUSIVE` | Silence, only circumstantial signals, or an uncalibrated run. |
| `SKIPPED` | Capability gap, setup turn, or a refused non-local target. |

## This folder must NEVER contain

- A real `reference_prompt` or `prompt_canary`. Both are operator-local and belong in
  `configs/plugins.yaml`; a test asserts the shipped manifest carries empty values.
- Executable payloads. Payloads are data, rendered by a non-evaluating loader (ADR-016).
- Destructive payloads.
- Imports of private core internals — packs use `sdk/` and `plugins/base/` only.
- Any special handling in the engine. Delete this directory and the engine still starts, still
  scans, and still reports, with a coverage gap recorded.
