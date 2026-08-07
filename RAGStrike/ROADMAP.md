# Roadmap

Milestones are summarized here. The authoritative version, with exit criteria and dependency notes,
is [`docs/annex-d-risk-roadmap.md`](docs/annex-d-risk-roadmap.md).

Every milestone has a **binary exit criterion** — a condition that is either met or not, never
"mostly."

---

## Phases to v1.0

| Phase  | Milestone                     | Exit criterion                                                                                                                   | Status     |
| ------ | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| **0**  | Architecture                  | SDD approved; every later phase implements against its contracts                                                                 | ✅ Complete |
| **1**  | Engineering foundation        | CI green on an empty codebase with **all gates active** — the dependency rule is enforced before there is any code to violate it | ✅ Complete |
| **2**  | VulnerableRAG v1              | Upload a PDF, ask a question, see retrieved chunks and sources; all nine documented weaknesses manually reproducible             | ⬜ Next     |
| **3**  | RAGStrike core                | `ragstrike scan` runs a hardcoded probe set end to end and persists evidence. No attack packs yet                                | ⬜          |
| **4**  | Plugin framework              | A fixture pack installed via pip is discovered, scheduled, and executed with **zero edits under `core/`**                        | ⬜          |
| **5**  | Attack SDK                    | A pack scaffolded by `sdk new-pack` passes conformance with no LLM, no network, no Docker                                        | ⬜          |
| **6**  | Analyzer, scoring, reporting  | A full scan produces a complete HTML report with all ten sections and a hand-reproducible risk score                             | ⬜          |
| **7**  | Injection packs               | Prompt injection, indirect injection, role override — all detect on VulnerableRAG, **zero** findings on SecureRAG                | ⬜          |
| **8**  | Leakage packs                 | Prompt leakage, secret extraction, PII leakage — same bidirectional criterion                                                    | ⬜          |
| **9**  | Context packs                 | Context injection, poisoning, window overflow — plus every poisoning case cleans up after itself                                 | ⬜          |
| **10** | Analyzer maturity + grounding | **SC1 met in CI**: VulnerableRAG grades E/F, SecureRAG grades A/B, per-category minimums enforced                                | ⬜          |
| **11** | v1.0 release                  | `pip install ragstrike` works from a clean machine; quickstart completes in under ten minutes                                    | ⬜          |

### The dependency that matters

**Phases 4 and 5 gate everything after them.** No attack pack should be written before the plugin
contract and the SDK conformance suite exist. Packs written earlier will encode assumptions the
contract does not guarantee, and the first contract change will break all of them simultaneously.

### The success criteria being built toward

| | Criterion |
|---|---|
| **SC1** | Differential correctness — VulnerableRAG grades E/F, SecureRAG A/B, enforced in CI |
| **SC2** | Extension without modification — a new pack requires zero core edits |
| **SC3** | Provider substitution — swapping the adapter changes no engine file |
| **SC4** | Determinism — same seed, same corpus, temperature-zero target → identical results |
| **SC5** | Explainability — every finding traces to exact request, response, detector, and arithmetic |

---

## After v1.0

### v1.x — consolidation

SARIF output for native code-scanning integration · LangChain and LlamaIndex adapters · additional
provider adapters · scheduled scans with regression alerting · report diffing UI · a community pack
index · localization of the string catalog.

### v2.0 — depth

| Item | Why it is v2 |
|---|---|
| **Plugin sandboxing** | Subprocess isolation with a capability broker, retiring the accepted risk that installing a pack grants full process trust |
| **Agentic target support (LLM06)** | Excessive-agency testing needs an action-side sandbox that records intended side effects without performing them |
| **Multimodal injection** | Instructions embedded in images, audio, and structured documents |
| **Adaptive attack generation** | Mutators that learn from what worked earlier in the same scan — within strict determinism-preserving bounds |
| **Embedding-space attacks** | Inversion and collision testing against the vector store directly |
| **Multi-turn crescendo** | Long-horizon escalation strategies |
| **Guardrail fingerprinting** | Identifying which defensive product a target uses, and testing its known boundaries |
| **Public benchmark corpus** | Versioned targets with expected grades, so RAGStrike's own accuracy can be measured by third parties |

---

## Permanently out of scope

Detection evasion · WAF bypass · rate-limit circumvention · mass or untargeted scanning · any feature
whose primary value is testing systems the operator is not authorized to test.

Recorded here so the boundary is not relitigated in every feature discussion.
