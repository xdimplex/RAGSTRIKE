<div align="center">

# SecureRAG

**The hardened half of a RAG security lab — the same application as VulnerableRAG, with the defences on**

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Status](https://img.shields.io/badge/status-hardened%20not%20audited-orange)](docs/security-features.md)

</div>

---

> ### ⚠️ Read this first
>
> **Hardened is not audited.** Every control here was written and tested against the attacks its
> author thought of. That is not the same claim as "safe to expose".
>
> SecureRAG ingests the same synthetic corpus as VulnerableRAG, planted canaries included, and it has
> **no authentication, no authorization, and no rate limiting** — all three are declared and
> deliberately not implemented. Run it on loopback. Never with real data.
>
> Both entry points refuse to start without `RAGSTRIKE_LAB_ACK=1`. See
> [`docs/LAB_SAFETY.md`](docs/LAB_SAFETY.md).

---

## Purpose

SecureRAG exists to be **compared**. It is a byte-for-byte copy of VulnerableRAG's architecture with
one thing changed: the security control chain is composed instead of empty.

That constraint is what makes the pair useful. RAGStrike's differential correctness criterion —
VulnerableRAG grades E/F, SecureRAG grades A/B — only measures *security* if everything except
security is held constant. So the endpoints are identical, the response schemas are identical, the
pipeline is identical, and benign questions are answered equivalently.

**SecureRAG's acceptance criterion is producing zero RAGStrike findings.** That is what makes the
scanner's false-positive rate measurable.

---

## Differences from VulnerableRAG

Two that matter, and one that shows.

**1. The control chain.** VulnerableRAG builds `SecurityPolicyChain([])`. SecureRAG builds seven
controls: context sanitizer, input validator, retrieval filter, session bounder, citation grounder,
output filter, secret masker. Composed **in code** — no configuration value can remove one.

**2. The prompt template.** VulnerableRAG concatenates the system prompt, the retrieved context, and
the question into one flat string with nothing to distinguish instruction from data. SecureRAG fences
and labels each region, states the instruction hierarchy twice, attaches provenance to every chunk,
and escapes the fence markers so a document cannot close the fence early.

**3. Its system prompt contains no credentials.** VulnerableRAG's carries an API key and a connection
string. Removing them is the cheapest fix in the application, and the one secret masking exists to
back up rather than replace.

The API difference is a single field: `GET /health?include_prompt=true` returns `null` here. The
field remains in the schema, because removing it would break a client written against the other half.

Full detail: [`docs/architecture-comparison.md`](docs/architecture-comparison.md).

---

## Shared architecture

```
PDF → Chunking → Embedding → ChromaDB → Retriever → Prompt Template → Ollama → Answer
```

FastAPI · Streamlit · Ollama · Qwen3 · LangChain · ChromaDB · SQLite — the same stack, the same
versions, the same pipeline module. Hardening enters entirely through the policy chain the pipeline
already called and the template it already used.

| | API | UI |
|---|---|---|
| VulnerableRAG | 9000 | 8601 |
| **SecureRAG** | **9001** | **8602** |

---

## How to run

```bash
pip install -e ".[ui,dev]"
ollama pull qwen3:4b && ollama pull nomic-embed-text

RAGSTRIKE_LAB_ACK=1 python -m profiles.secure.main_api    # http://127.0.0.1:9001
RAGSTRIKE_LAB_ACK=1 python -m profiles.secure.main_ui     # http://127.0.0.1:8602
```

[`docs/deployment-guide.md`](docs/deployment-guide.md) covers running both halves side by side.

---

## How to compare

Start both, seed both with the same corpus, then ask the same question of each:

```bash
curl -s localhost:9000/chat -H 'content-type: application/json' \
  -d '{"message":"What is the remote work policy?","include_prompt":true}' | jq -r .prompt

curl -s localhost:9001/chat -H 'content-type: application/json' \
  -d '{"message":"What is the remote work policy?","include_prompt":true}' | jq -r .prompt
```

The prompts are the lesson. One is a flat string; the other is fenced, labelled, and attributed.

Or read the diff directly — the shortest and most instructive one first:

```bash
diff VulnerableRAG/profiles/vulnerable/prompts/system_prompt.txt \
     SecureRAG/profiles/secure/prompts/system_prompt.txt

diff VulnerableRAG/rag/generation/prompt_builder.py \
     SecureRAG/rag/generation/prompt_builder.py
```

With RAGStrike:

```bash
ragstrike scan --target vulnerable-rag
ragstrike scan --target secure-rag
```

RAGStrike needs no modification — same API, same declared capabilities, same negotiation.

---

## Security objectives

| Objective | Where |
|---|---|
| Input validation | `InputValidator`, plus a boundary check in front of the embedder |
| Prompt template hardening | `rag/generation/prompt_builder.py` |
| Context boundary enforcement | Fencing, provenance labelling, fence escaping |
| Output validation | `OutputFilter` — length, normalization, system-prompt echo |
| Secret masking | `SecretMasker`, last in the chain, with fingerprints |
| Structured error handling | One error table; every response is JSON in one envelope |
| Configuration validation | `rag/security_config.py`, bounded and fail-fast |
| Logging improvements | Reasons and fingerprints, never document or answer text |
| Document upload validation | `backend/validation.py` — size, extension, MIME, magic bytes |
| Rate limiting / auth / authz | **Declared, not implemented.** `future_controls.py` |

The last row is the important one. Those three are excluded from the chain by construction and named
in `GET /health` as not implemented, because a control listed as active but doing nothing tells an
operator they are covered when they are not.

---

## Tests

```bash
pytest                    # 248
pytest tests/parity       # the drift gate: same endpoints, same schemas
pytest tests/regression   # the nine weaknesses, asserted absent
```

The suite runs with Ollama stopped.

---

## Documentation

[`docs/`](docs/README.md) — architecture comparison, security features, configuration, deployment,
compatibility, migration, developer guide, folder responsibilities.

Start with [`docs/security-features.md`](docs/security-features.md), and read its final section on
what SecureRAG does *not* do.

---

## License

Apache-2.0. Not published to PyPI — the packaging metadata marks it `Private :: Do Not Upload`.
