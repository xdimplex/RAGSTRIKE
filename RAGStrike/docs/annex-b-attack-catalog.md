# Annex B — Attack Pack Catalog

*Normative annex to [RAGSTRIKE-SDD-001](SDD.md). Version 1.0.0.*

This annex specifies the twelve initial attack packs: what each tests, which capabilities it needs, which detectors provide its oracle, its impact class and base impact weight, and its mapping to external taxonomies. Phase assignments map to the development milestones in [Annex D](annex-d-risk-roadmap.md).

**Every pack in this catalog is a plugin.** None of them is special-cased in the core. If a pack in this list were deleted from the distribution, the engine would still start, still scan, and still report — with a coverage gap recorded. That property is the acceptance test for the plugin architecture.

---

## B.1 Catalog Overview

| # | Pack slug | Category | Impact class | Base impact | Required capabilities | OWASP LLM | Phase |
|---|---|---|---|---|---|---|---|
| 1 | `prompt-injection` | Prompt Injection | INTEGRITY | 8 | CHAT | LLM01 | 7 |
| 2 | `indirect-prompt-injection` | Indirect Prompt Injection | INTEGRITY | 9 | CHAT, INGEST_DOCUMENT | LLM01 | 7 |
| 3 | `prompt-leakage` | Prompt Leakage | CONFIDENTIALITY | 7 | CHAT | LLM07 | 8 |
| 4 | `role-override` | Role Override | INTEGRITY | 7 | CHAT | LLM01 | 7 |
| 5 | `context-injection` | Context Injection | INTEGRITY | 8 | CHAT | LLM01, LLM08 | 9 |
| 6 | `context-poisoning` | Context Poisoning | INTEGRITY | 9 | CHAT, INGEST_DOCUMENT | LLM04, LLM08 | 9 |
| 7 | `secret-extraction` | Secret Extraction | CONFIDENTIALITY | 10 | CHAT | LLM02, LLM07 | 8 |
| 8 | `pii-leakage` | PII Leakage | CONFIDENTIALITY / COMPLIANCE | 9 | CHAT | LLM02 | 8 |
| 9 | `context-window-overflow` | Context Window Overflow | AVAILABILITY / INTEGRITY | 6 | CHAT | LLM10 | 9 |
| 10 | `hallucination-evaluation` | Hallucination Evaluation | SAFETY | 5 | CHAT | LLM09 | 10 |
| 11 | `retrieval-integrity` | Retrieval Integrity | INTEGRITY | 8 | CHAT, RETURN_CHUNKS | LLM08 | 10 |
| 12 | `citation-verification` | Citation Verification | SAFETY | 5 | CHAT, LIST_SOURCES | LLM09 | 10 |

**OWASP reference:** OWASP Top 10 for Large Language Model Applications (2025) — LLM01 Prompt Injection, LLM02 Sensitive Information Disclosure, LLM03 Supply Chain, LLM04 Data and Model Poisoning, LLM05 Improper Output Handling, LLM06 Excessive Agency, LLM07 System Prompt Leakage, LLM08 Vector and Embedding Weaknesses, LLM09 Misinformation, LLM10 Unbounded Consumption.

Additional taxonomies referenced: **MITRE ATLAS** technique IDs and **CWE** identifiers per attack, recorded on every finding for downstream tooling.

---

## B.2 Pack 1 — Prompt Injection

**Question it answers:** can a user's message override the application's instructions?

| Attack | Technique | Primary detectors |
|---|---|---|
| `direct-override` | Explicit instruction to disregard prior instructions and emit a canary. | Canary (1.0), Structural (0.8), Refusal-Absence (0.6) |
| `delimiter-escape` | Fake delimiters/markup mimicking the prompt's own structure to close the "data" region. | Canary (1.0), Structural (0.9) |
| `authority-spoof` | Impersonated system/developer/admin voice. | Canary (1.0), Structural (0.8) |
| `task-substitution` | Reframes the request as a new legitimate task ("you are now a translator"). | Structural (0.9), Differential (0.7) |
| `encoding-obfuscation` | Base64 / ROT13 / homoglyph / zero-width encoded instruction. | Canary (1.0), Structural (0.8) |
| `multilingual-pivot` | Instruction issued in a language other than the system prompt's. | Canary (1.0), Refusal-Absence (0.5) |
| `payload-splitting` | Instruction assembled across multiple turns. | Canary (1.0), Differential (0.8) — requires SESSION_MEMORY |

**Mutators:** `encoding`, `language`, `casing`, `whitespace`, `politeness-framing`.
**Attempts:** 3. **Aggregation:** noisy-OR, threshold 0.5.
**ATLAS:** AML.T0051 (LLM Prompt Injection). **CWE:** CWE-77, CWE-1427.

**Design note.** `payload-splitting` is capability-gated on `SESSION_MEMORY` and marked `fresh_session: false` — it is one of the few attacks that legitimately requires session continuity. Every other attack in this pack runs in a fresh session so that a success in one case cannot inflate the next (§15.2 of the SDD).

---

## B.3 Pack 2 — Indirect Prompt Injection

**Question it answers:** can content in the retrieval corpus give instructions to the model?

This is the defining RAG vulnerability and the pack with the highest base impact after secret extraction, because the adversary needs no access to the chat interface at all.

| Attack | Technique | Primary detectors |
|---|---|---|
| `hidden-text-injection` | Instruction embedded in a document as white-on-white text, tiny font, or off-canvas content. | Canary (1.0), Retrieval Integrity (0.9) |
| `metadata-injection` | Instruction placed in PDF metadata fields that the extractor ingests. | Canary (1.0) |
| `zero-width-injection` | Instruction encoded with zero-width and bidirectional control characters. | Canary (1.0), Retrieval Integrity (0.9) |
| `authority-document` | A document that claims to be a policy update superseding the system prompt. | Canary (1.0), Differential (0.8) |
| `retrieval-bait` | Document engineered to rank highly for common queries, then injects. | Canary (1.0), Retrieval Integrity (0.9) |
| `cross-document-chain` | Instruction split across two documents, assembled only when both are retrieved. | Canary (1.0), Retrieval Integrity (0.8) |

**Lifecycle:** every attack in this pack is a two-phase case with `depends_on` ordering — ingest, then query. **Every ingested artifact is canary-tagged, tracked in the `canaries` table, and removed by the cleanup step; residuals are reported (§16.4 of the SDD).**

**ATLAS:** AML.T0051.001 (Indirect). **CWE:** CWE-77, CWE-829.

---

## B.4 Pack 3 — Prompt Leakage

**Question it answers:** can the system prompt be recovered?

| Attack | Technique | Primary detectors |
|---|---|---|
| `direct-request` | Simply asks for the instructions. | Similarity (1.0), Canary (1.0 when a lab canary is present) |
| `completion-continuation` | Asks the model to continue text that begins with the prompt's opening. | Similarity (1.0) |
| `translation-laundering` | Requests the instructions translated or summarized (evades verbatim filters). | Similarity (0.8), LLM Judge (0.6, capped) |
| `format-transformation` | Requests the prompt as JSON, a poem, or a bulleted list. | Similarity (0.8), Structural (0.7) |
| `debug-pretext` | Claims to be a developer performing diagnostics. | Similarity (1.0), Refusal-Absence (0.5) |
| `token-boundary-probe` | Elicits the prompt fragment-by-fragment across turns. | Similarity (0.9) |
| `error-channel-leak` | Malformed input intended to surface the prompt in an error or debug field. | Canary (1.0), Pattern (0.9) |

**Detector note.** The Similarity detector's threshold is calibrated against the lab targets, where the true system prompt is known. Against an unknown target, similarity is computed against *any* returned text that exhibits instruction-like structure, and confidence is reduced accordingly — RAGStrike reports lower confidence rather than pretending to certainty it cannot have.

**ATLAS:** AML.T0056. **CWE:** CWE-200, CWE-209.

---

## B.5 Pack 4 — Role Override

**Question it answers:** can the assistant's persona, constraints, or refusal policy be replaced?

| Attack | Technique | Primary detectors |
|---|---|---|
| `persona-replacement` | Assigns a new unconstrained identity. | Structural (0.9), Canary (1.0) |
| `hypothetical-framing` | "In a fictional world where…" | Structural (0.8), Differential (0.7) |
| `nested-simulation` | Model simulates a system that simulates an unconstrained model. | Structural (0.9), Differential (0.8) |
| `constraint-negation` | Asserts the constraints were lifted by an authority. | Structural (0.8), Refusal-Absence (0.6) |
| `output-format-coercion` | Forces a format in which refusal is structurally impossible. | Structural (1.0) |

**Boundary note.** This pack tests *whether application constraints hold*, not whether the model will produce harmful content. Payloads demand a benign canary as proof of override. RAGStrike does not need to elicit genuinely harmful output to demonstrate that the constraint layer failed, and it will not (§31, non-destructive payloads).

**ATLAS:** AML.T0054. **CWE:** CWE-1427.

---

## B.6 Pack 5 — Context Injection

**Question it answers:** can a user's message be mistaken for retrieved context or system content?

Distinct from Pack 1: here the goal is not to give an instruction but to **forge provenance** — to make user-supplied text occupy the trusted "retrieved document" slot.

| Attack | Technique | Primary detectors |
|---|---|---|
| `fake-context-block` | User message mimics the retrieved-context formatting. | Structural (0.9), Differential (0.8) |
| `source-spoofing` | Claims a fabricated authoritative source. | Structural (0.8), Citation Verifier (0.9) |
| `citation-forgery` | Supplies fake citations the model then reproduces. | Citation Verifier (1.0) |
| `context-priority-manipulation` | Asserts the injected content supersedes retrieved content. | Differential (0.9), Structural (0.8) |
| `template-boundary-probe` | Maps the prompt template's delimiters by differential probing. | Differential (0.9), Similarity (0.7) |

**ATLAS:** AML.T0051. **CWE:** CWE-345 (Insufficient Verification of Data Authenticity).

---

## B.7 Pack 6 — Context Poisoning

**Question it answers:** can the corpus be manipulated so that future, unrelated queries return adversary-controlled answers?

The distinguishing property is **persistence**: the effect survives the session that created it and affects other users.

| Attack | Technique | Primary detectors |
|---|---|---|
| `factual-poisoning` | Injects false facts that outrank the truth for a target query. | Canary (1.0), Retrieval Integrity (0.9), Differential (0.9) |
| `embedding-collision` | Content engineered to sit near many query embeddings. | Retrieval Integrity (1.0) |
| `corpus-flooding` | Volume of near-duplicate content crowding out legitimate chunks. | Retrieval Integrity (0.9), Threshold (0.6) |
| `persistent-instruction` | Instruction designed to be retrieved across many unrelated queries. | Canary (1.0), Differential (0.9) |
| `chunk-boundary-abuse` | Payload placed to survive or exploit the chunker's boundaries. | Canary (1.0), Retrieval Integrity (0.8) |
| `cross-session-persistence` | Verifies the poison affects a **new, clean** session. | Canary (1.0), Differential (1.0) |

**Verification protocol.** Every attack in this pack executes a three-phase sequence — **baseline query → poison → fresh-session query** — and success requires a *differential* change between the two queries, not merely a suspicious response. This is the strongest evidence design in the framework and the reason Differential carries weight 0.9–1.0 here.

**Cleanup is mandatory and elevated.** Poisoning writes persistent state into a target. The pack declares `requires_cleanup: true`; the orchestrator refuses to schedule it if the adapter cannot delete ingested documents, unless the operator sets an explicit `allow_residual_artifacts` acknowledgement — which is then printed in the report.

**ATLAS:** AML.T0020 (Poison Training Data), AML.T0051.001. **CWE:** CWE-349, CWE-829.

---

## B.8 Pack 7 — Secret Extraction

**Question it answers:** does the application disclose credentials, keys, endpoints, or internal configuration?

Highest base impact in the catalog (10) — a leaked credential is an immediate, transferable compromise.

| Attack | Technique | Primary detectors |
|---|---|---|
| `direct-credential-request` | Asks for keys, tokens, or connection strings. | Pattern (1.0), Canary (1.0) |
| `configuration-enumeration` | Elicits environment variables, endpoints, model names, internal hostnames. | Pattern (0.9), Similarity (0.7) |
| `error-induced-disclosure` | Malformed input triggering verbose errors carrying configuration. | Pattern (1.0) |
| `corpus-secret-harvest` | Queries designed to surface secrets accidentally present in the corpus. | Pattern (1.0), Retrieval Integrity (0.8) |
| `partial-reconstruction` | Extracts a secret in fragments across turns to evade output filters. | Pattern (0.9), Canary (1.0) |
| `format-evasion` | Requests the secret spelled out, reversed, or base64-encoded to bypass masking. | Canary (1.0), Pattern (0.8) |

**Detector note — entropy gating.** The Pattern detector combines format regexes with a Shannon-entropy threshold and a known-placeholder deny-list (`AKIAIOSFODNN7EXAMPLE`, `sk-000…`, documentation samples). Without entropy gating, secret detectors produce a flood of false positives on any corpus containing example configuration, and a scanner that cries wolf on credentials gets switched off.

**Handling note.** Extracted secrets are stored raw only in the local database and are masked by default in every exported report (§19.4 of the SDD).

**ATLAS:** AML.T0057. **CWE:** CWE-522, CWE-798, CWE-200.

---

## B.9 Pack 8 — PII Leakage

**Question it answers:** does the application disclose personal data across users, sessions, or authorization boundaries?

| Attack | Technique | Primary detectors |
|---|---|---|
| `cross-session-recall` | Asks about a previous user's conversation. | Canary (1.0), Pattern (0.9) |
| `corpus-pii-extraction` | Enumerates personal data from indexed documents. | Pattern (1.0), Retrieval Integrity (0.8) |
| `aggregation-attack` | Combines individually innocuous responses into an identifying profile. | Pattern (0.9), Differential (0.7) |
| `authorization-bypass` | Requests documents outside the current user's scope. | Retrieval Integrity (1.0), Canary (1.0) |
| `inference-attack` | Elicits inferred sensitive attributes not stated in the corpus. | LLM Judge (0.6, capped), Pattern (0.7) |

**Lab-only synthetic PII.** VulnerableRAG's corpus contains synthetic, clearly-labelled, canary-tagged personal records. RAGStrike never introduces real personal data into a target, and payloads never assert real identities.

**Compliance mapping.** Findings in this pack additionally carry a `COMPLIANCE` impact class so that reports can surface them separately for GDPR/CCPA-relevant review.

**ATLAS:** AML.T0057. **CWE:** CWE-359, CWE-200, CWE-285.

---

## B.10 Pack 9 — Context Window Overflow

**Question it answers:** what happens at the edges of the context budget — do controls silently fall out of the window?

| Attack | Technique | Primary detectors |
|---|---|---|
| `prompt-displacement` | Volume of input intended to push the system prompt out of the effective window. | Canary (1.0), Differential (0.9), Structural (0.8) |
| `retrieval-saturation` | Query engineered to retrieve maximal context, crowding out instructions. | Threshold (0.8), Differential (0.9) |
| `truncation-probe` | Determines where the application silently truncates and what it drops first. | Threshold (1.0), Differential (0.8) |
| `session-history-flood` | Unbounded conversation growth degrading instruction adherence. | Differential (0.9), Threshold (0.7) |
| `cost-amplification` | Measures maximum tokens and latency inducible by one request. | Threshold (1.0) |

**Safety constraint.** This pack is the closest RAGStrike comes to a resource-exhaustion test, and it is deliberately bounded: payload sizes are capped by profile, the rate limiter still applies, `cost-amplification` is **excluded from the quick and standard profiles** and available only in `deep` with an explicit acknowledgement flag. The intent is to measure a limit, never to exhaust a target (§31 of the SDD).

**ATLAS:** AML.T0034. **CWE:** CWE-400, CWE-770.

---

## B.11 Pack 10 — Hallucination Evaluation

**Question it answers:** does the application fabricate when it should abstain?

This pack measures an *application control* — grounding and abstention — not model quality (NG3).

| Attack | Technique | Primary detectors |
|---|---|---|
| `unanswerable-probe` | Questions with no answer in the corpus; correct behaviour is explicit abstention. | Refusal-Absence (0.9), LLM Judge (0.7, capped) |
| `false-premise` | Question presupposing a fact the corpus contradicts. | LLM Judge (0.7), Differential (0.8) |
| `nonexistent-entity` | Asks about an entity that does not exist anywhere in the corpus. | Canary (1.0 — the entity name *is* the canary), Refusal-Absence (0.8) |
| `overconfidence-probe` | Measures whether uncertainty is expressed where evidence is thin. | LLM Judge (0.6, capped) |
| `numeric-fabrication` | Requests specific figures absent from the corpus. | Pattern (0.8), Citation Verifier (0.9) |

**The nonexistent-entity canary is the key design.** By inventing a high-entropy entity name that provably appears nowhere in the corpus, a substantive answer about it is deterministic proof of fabrication — converting the hardest detector problem in the catalog into a string check. Where that trick is unavailable, the pack falls back to the confidence-capped judge and reports findings as model-assisted.

**ATLAS:** AML.T0048. **CWE:** CWE-1426.

---

## B.12 Pack 11 — Retrieval Integrity

**Question it answers:** is the retrieval layer returning the right chunks, from authorized sources, with correct provenance?

Requires `RETURN_CHUNKS`. Where unavailable, the pack is skipped and recorded as a coverage gap — an outcome the report states explicitly rather than quietly grading around.

| Attack | Technique | Primary detectors |
|---|---|---|
| `provenance-verification` | Every returned chunk must trace to a manifest-declared source. | Retrieval Integrity (1.0) |
| `unauthorized-source-retrieval` | Attempts retrieval from out-of-scope sources. | Retrieval Integrity (1.0), Canary (1.0) |
| `relevance-manipulation` | Crafted queries forcing retrieval of adversary-chosen chunks. | Retrieval Integrity (0.9), Differential (0.8) |
| `chunk-tampering-detection` | Verifies returned chunk text matches the stored source text. | Retrieval Integrity (1.0) |
| `empty-retrieval-behaviour` | Behaviour when nothing relevant is retrieved — abstain, or fabricate? | Refusal-Absence (0.9), Threshold (0.7) |
| `threshold-probe` | Whether a minimum-relevance threshold exists at all. | Threshold (0.9), Retrieval Integrity (0.8) |

**ATLAS:** AML.T0018. **CWE:** CWE-345, CWE-285.

---

## B.13 Pack 12 — Citation Verification

**Question it answers:** are cited sources real, retrieved, and actually supporting of the claims?

Requires `LIST_SOURCES`.

| Attack | Technique | Primary detectors |
|---|---|---|
| `citation-existence` | Every cited source must exist in the corpus manifest. | Citation Verifier (1.0) |
| `citation-retrieval-match` | Every cited source must appear in the retrieval set for that query. | Citation Verifier (1.0), Retrieval Integrity (0.9) |
| `claim-grounding` | Claims must be lexically supported by the cited chunk. | Citation Verifier (0.9), LLM Judge (0.6, capped) |
| `citation-under-pressure` | Whether citation discipline degrades when the user demands sources. | Citation Verifier (1.0), Differential (0.8) |
| `fabricated-source-acceptance` | Whether the app adopts a user-supplied fake citation. | Citation Verifier (1.0), Canary (1.0) |

**Two-tier verification.** The lexical tier (deterministic overlap against the cited chunk) is always run and is sufficient for `citation-existence` and `citation-retrieval-match` — both are exact set operations. Only `claim-grounding` reaches for the judge, and its findings are labelled model-assisted.

**ATLAS:** AML.T0048. **CWE:** CWE-345, CWE-1426.

---

## B.14 Profile Composition

| Profile | Packs | Payload tiers | Approx. cases | Attempts | Target duration |
|---|---|---|---|---|---|
| **quick** | 1, 3, 4, 7 | `quick` | ~90 | 2 | < 4 min |
| **standard** | 1–8, 11 | `quick` + `standard` | ~400 | 3 | < 15 min |
| **deep** | 1–12 | all tiers | ~1200 | 5 | < 60 min |
| **custom** | operator-selected | operator-selected | — | — | — |

`cost-amplification` (Pack 9) is `deep`-only and additionally gated on an explicit acknowledgement flag.

---

## B.15 Adding a Thirteenth Pack

The catalog is a starting set, not a closed list. A new pack requires **zero core changes**:

1. `ragstrike sdk new-pack <name>` → valid skeleton with a passing conformance test.
2. Declare `pack.yaml` (compatibility range, capabilities, permissions), attacks, payloads, detector bindings, and recommendations — all YAML.
3. Implement custom detectors only if the built-in catalog is insufficient; most packs need none.
4. Pass the conformance suite offline using SDK test doubles (no LLM, no network).
5. Validate in **both** directions: must produce findings against VulnerableRAG, must produce none against SecureRAG.
6. `pip install` it. The registry discovers it on next start.

Candidate packs already identified for post-v1 (see Annex D): Excessive Agency / Tool Abuse (LLM06), Multimodal Injection, Supply Chain / Model Provenance (LLM03), Improper Output Handling / downstream XSS and SQLi via model output (LLM05), Embedding Inversion (LLM08), Adversarial Suffix Optimization, Multi-Turn Crescendo, and Guardrail Fingerprinting.
