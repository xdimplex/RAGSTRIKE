# Folder responsibilities

Inherited from VulnerableRAG unless the **Diverges** column says otherwise. A file in a folder marked
"no" that has been edited is drift — see [`compatibility-guide.md`](compatibility-guide.md).

| Folder | Owns | Diverges |
|---|---|---|
| `backend/` | The FastAPI app: application factory, dependency wiring, the error → HTTP table, the always-JSON guarantee | partly |
| `backend/routers/` | One module per resource. Translate; never decide | `upload`, `chat`, `health` |
| `backend/schemas/` | Pydantic request/response models. **The API contract** | **no** |
| `backend/middleware/` | CORS, request logging, security headers, rate-limit counter | `security.py` is new |
| `backend/validation.py` | Upload validation at the boundary, in front of the parser | **new** |
| `rag/` | The pipeline. Framework-free below the routers | partly |
| `rag/config.py` | Layered YAML load and validation | 4 lines |
| `rag/security_config.py` | The `security.yaml` schema | **new** |
| `rag/generation/prompt_builder.py` | Prompt assembly | **the biggest diff** |
| `rag/generation/pipeline.py` | The query pipeline and its hook calls | **no** |
| `rag/ingestion/` | PDF loading, chunking, embedding | **no** |
| `rag/retrieval/` | Similarity search | **no** |
| `rag/session/` | Conversation memory | **no** |
| `rag/policy/` | The `SecurityPolicy` contract, hooks, and chain | **no** |
| `rag/policy/controls/` | **One module per defence.** The entire difference between the two applications | **new** |
| `rag/models.py`, `rag/errors.py` | Domain objects and the error taxonomy | **no** |
| `database/` | SQLite connection, migrations, repositories | **no** |
| `vectorstore/` | ChromaDB client and collections | **no** |
| `frontend/` | The Streamlit UI | **no** |
| `profiles/secure/` | Chain composition, system prompt, ports, entry points | **the application** |
| `configs/` | Shared configuration, logging, and `security.yaml` | `security.yaml` is new |
| `corpus/` | Synthetic documents with planted canaries | **no** |
| `uploads/`, `data/`, `vectorstore/chroma/`, `logs/` | Runtime state. Not in version control | — |
| `scripts/` | Corpus seeding, PDF generation, lab reset | **no** |
| `tests/` | unit · integration · parity · regression | inverted + 5 new suites |
| `docs/` | These guides | rewritten |
| `assets/` | Diagrams and screenshots | **no** |

---

## Rules that hold everywhere

**`backend/` never contains pipeline logic.** Routers translate HTTP into a call and back.

**`rag/` never imports FastAPI.** The pipeline is usable from a script, a test, or a future worker.

**`rag/policy/controls/` never contains profile detection.** A policy that asks which profile
assembled it has broken the seam that makes the pair comparable.

**`backend/schemas/` is the API contract.** Changing a field name there breaks compatibility with
VulnerableRAG, and `tests/parity` will say so.

**Nothing outside `profiles/` composes a chain.** One place, in code.
