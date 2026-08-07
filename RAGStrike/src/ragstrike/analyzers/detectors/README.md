# `analyzers.detectors` — Built-in Detector Catalog

> **Layer:** 2 — Application  ·  **SDD reference:** [SDD §16.3](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The shared detector library. Attack packs bind these declaratively by id and weight in their attack definitions, so most packs need to write no detector code at all. Improving a detector here improves every pack that binds it.

## Responsibilities

- **Deterministic detectors** (the backbone): canary, pattern/secret, PII, similarity, refusal-absence, structural, retrieval-integrity, citation-verifier, differential, threshold.
- **One nondeterministic detector**: the LLM judge — off by default, confidence-capped at 0.7, never sufficient alone, and every finding depending on it is labelled model-assisted.
- Entropy gating and known-placeholder deny-lists on secret patterns, because a detector that cries wolf on documentation samples gets switched off.

## Files that will exist here later

| File | Responsibility | Phase |
|---|---|---|
| `canary.py` | Exact high-entropy token match — the primary oracle (ADR-005) | 6 |
| `pattern.py / secret_patterns.py / pii_patterns.py` | Regex library with entropy gating | 8 |
| `similarity.py` | Token and n-gram overlap against a known prompt or chunk | 8 |
| `refusal_absence.py` | Refusal lexicon — a supporting signal, never sufficient alone | 6 |
| `structural.py` | Format, role, and marker compliance | 7 |
| `retrieval_integrity.py` | Chunk provenance against the corpus manifest | 10 |
| `citation_verifier.py` | Citation existence, retrieval match, lexical grounding | 10 |
| `differential.py` | Attack response vs benign baseline | 10 |
| `threshold.py` | Latency, token count, truncation | 9 |
| `llm_judge.py` | Constrained local judge — temperature 0, forced structured output | 10 |

## This folder must NEVER contain

- Impure detectors — no network calls except the explicitly-declared judge, no clock reads, no hidden state.
- A detector that returns a bare boolean; every detector returns a `Signal` with confidence and rationale.
- Raising the judge's confidence cap above 0.7.
