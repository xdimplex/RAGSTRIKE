# Architecture diagrams

Mermaid source. Renders in GitHub as-is; export to SVG for slides.

---

## 1 · The three components

```mermaid
graph LR
    subgraph Lab
        V[VulnerableRAG<br/>:9000]
        S[SecureRAG<br/>:9001]
    end
    R[RAGStrike<br/>scanner] -->|HTTP, read only| V
    R -->|HTTP, read only| S
    V -.identical corpus.- S
    R --> REP[Report<br/>HTML · MD · JSON]
```

**The dotted line is the load-bearing part.** Identical corpus, identical API surface, opposite
security posture — that is what makes a comparison mean anything.

## 2 · Layers

```mermaid
graph TD
    subgraph L1[interface]
        CLI[cli] --- DASH[dashboard] --- API[api]
    end
    subgraph L2[application]
        CORE[core] --- ANA[analyzers] --- REP[reporters]
    end
    subgraph L3[adapters]
        PLUG[plugins] --- ADAPT[adapters] --- DB[database]
    end
    subgraph L4[domain]
        MOD[models] --- CFG[config] --- LOG[logging]
    end
    L1 --> L2 --> L3 --> L4
```

Dependencies point down, only. **Six `import-linter` contracts enforce this; the build fails on
violation.**

Modules on the same row are **siblings and may not import each other**. Indirect chains count:
`reporters → analyzers → models` breaks a contract with no individually suspicious import.

## 3 · A scan

```mermaid
sequenceDiagram
    participant U as User
    participant E as ScanEngine
    participant P as Plugin
    participant T as Target
    participant A as Analyzer

    U->>E: ragstrike scan --target vulnerable-rag
    E->>E: authorization record? local URL?
    E->>P: setup()
    P-->>E: payloads()  (deterministic)
    loop each payload
        E->>T: HTTP question
        T-->>E: answer
        E->>P: execute() → raw evidence
    end
    E->>P: analyze()  (pure — no network, clock, randomness)
    P-->>A: observations
    A->>A: detectors → confidence → risk score
    A-->>E: Findings (+ coverage, + skips with reasons)
    E->>P: cleanup()  (always, even on failure)
    E-->>U: report
```

`payloads()` deterministic ⇒ the scan is reproducible. `analyze()` pure ⇒ recorded evidence can be
re-analysed offline after a detector change, without re-attacking the target.

## 4 · A plugin

```mermaid
graph LR
    M[metadata.yaml] -->|read FIRST| REG[Registry]
    REG -->|compatible?<br/>capabilities?| DEC{admit}
    DEC -->|no| REF[refuse<br/>with a reason]
    DEC -->|yes| IMP[import plugin.py]
    IMP --> RUN[run]
    PAY[payloads/*.yaml] --> RUN
```

**The manifest is read before any plugin code is imported** (ADR-003). An incompatible pack is refused
with a reason rather than imported and crashed — which is also why a broken third-party pack cannot
take discovery down.

## 5 · SecureRAG's policy chain

```mermaid
graph TD
    D[document] --> H1[on_ingest]
    H1 --> C[chunk] --> H2[on_chunk]
    H2 --> VS[(vector store)]
    Q[question] --> RET[retrieve] --> H3[on_context_assembly]
    H3 --> H4[on_prompt_build] --> LLM[model]
    LLM --> H5[on_response] --> ANS[answer]
```

Five hooks. VulnerableRAG has the same pipeline with none of them.

**A note the diagram cannot show:** `on_context_assembly` fires *after* retrieval, so it is too late to
reject an over-long question — that check belongs at the HTTP boundary, and putting it in the hook was
a real bug.

## 6 · The dashboard

```mermaid
graph LR
    UI[Streamlit pages] --> TR{BackendTransport}
    TR -->|HttpTransport| API[/api/v1/]
    TR -->|DemoTransport| FIX[labelled fixtures]
    API -.not implemented.-> OFF[BACKEND OFFLINE]
```

The dashboard **never imports the engine** (ADR-010). It reports offline rather than silently serving
fixtures — plausible numbers presented as real are worse than no numbers.
